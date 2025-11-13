# core/bot/handlers/report.py
from datetime import date, timedelta, datetime
from asgiref.sync import sync_to_async
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import MessageHandler, filters, ConversationHandler, ContextTypes
from django.db.models import Sum, Count, Q

from core.models import FuelRecord, Car, Region, Zone, User
from core.refuel_bot.utils.validate_state_plate import normalize_plate_input, is_valid_plate


# ===== Клавиатуры подменю =====
def kb_reports_root():
    return ReplyKeyboardMarkup(
        [
            ["📆 По периоду", "🧭 По параметрам"],
            ["🔙 Назад", "❌ Отмена"],
        ],
        resize_keyboard=True
    )


def kb_reports_period():
    return ReplyKeyboardMarkup(
        [
            ["📅 Сегодня", "📅 Вчера"],
            ["📅 Неделя", "📅 Месяц"],
            ["📅 Произвольная дата"],
            ["🔙 Назад", "❌ Отмена"],
        ],
        resize_keyboard=True
    )


def kb_reports_filters():
    return ReplyKeyboardMarkup(
        [
            ["🚗 По машине", "👤 По заправщику"],
            ["🗺️ По региону", "📍 По зоне"],
            ["🔙 Назад", "❌ Отмена"],
        ],
        resize_keyboard=True
    )


# ===== Роль =====
@sync_to_async
def is_manager_or_admin(user):
    if not user:
        return False
    return user.is_superuser or user.groups.filter(name__in=["Менеджер", "Администратор"]).exists()


# ===== Агрегаторы =====
@sync_to_async
def aggregate_period_text(start, end):
    agg = FuelRecord.objects.filter(
        filled_at__date__gte=start,
        filled_at__date__lte=end
    ).aggregate(total=Sum("liters"), cnt=Count("id"))
    total = float(agg["total"] or 0)
    cnt = int(agg["cnt"] or 0)
    return f"📊 Отчёт за {start} — {end}\nВсего литров: {total:.1f} л\nЗаписей: {cnt}"


@sync_to_async
def aggregate_car_text(plate):
    car = Car.objects.filter(state_number__iexact=plate).first()
    if not car:
        return None, "Автомобиль не найден."
    agg = FuelRecord.objects.filter(car=car).aggregate(total=Sum("liters"), cnt=Count("id"))
    total = float(agg["total"] or 0)
    cnt = int(agg["cnt"] or 0)
    return car, f"🚗 {car.state_number} — всего {total:.1f} л, записей: {cnt}"


@sync_to_async
def aggregate_region_text(name):
    region = Region.objects.filter(name__iexact=name).first()
    if not region:
        return None, "Регион не найден."
    agg = FuelRecord.objects.filter(car__region=region).aggregate(total=Sum("liters"), cnt=Count("id"))
    total = float(agg["total"] or 0)
    cnt = int(agg["cnt"] or 0)
    return region, f"🗺️ {region.name} — всего {total:.1f} л, записей: {cnt}"


@sync_to_async
def aggregate_zone_text(text):
    zone = Zone.objects.filter(Q(name__iexact=text) | Q(code__iexact=text)).first()
    if not zone:
        return None, "Зона не найдена."
    agg = FuelRecord.objects.filter(employee__zone=zone).aggregate(total=Sum("liters"), cnt=Count("id"))
    total = float(agg["total"] or 0)
    cnt = int(agg["cnt"] or 0)
    return zone, f"📍 {zone.name} — всего {total:.1f} л, записей: {cnt}"


@sync_to_async
def aggregate_employee_text(text):
    user = None
    # сначала попробуем как telegram_id
    try:
        tg_id = int(text)
        user = User.objects.filter(telegram_id=tg_id).first()
    except Exception:
        pass
    if user is None:
        # username без @ или ФИО (частично)
        uq = text.lstrip("@")
        user = User.objects.filter(Q(username__iexact=uq) | Q(last_name__icontains=text) | Q(first_name__icontains=text)).first()
    if not user:
        return None, "Заправщик не найден."
    agg = FuelRecord.objects.filter(employee=user).aggregate(total=Sum("liters"), cnt=Count("id"))
    total = float(agg["total"] or 0)
    cnt = int(agg["cnt"] or 0)
    who = user.get_full_name() or user.username or user.telegram_id
    return user, f"👤 {who} — всего {total:.1f} л, записей: {cnt}"


# ===== Состояния =====
REPORTS_ROOT, REPORTS_PERIOD, REPORTS_FILTERS, PERIOD_FREE_INPUT, CAR_INPUT, REGION_INPUT, ZONE_INPUT, EMPLOYEE_INPUT = range(8)


# Вход в подменю "Отчёты"
async def open_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    if not await is_manager_or_admin(user):
        await update.message.reply_text("⛔ Доступ к отчётам только для менеджеров и администраторов.")
        return ConversationHandler.END

    await update.message.reply_text("Раздел отчётов. Выберите категорию:", reply_markup=kb_reports_root())
    return REPORTS_ROOT


# Роутер корня
async def reports_root_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text == "📆 По периоду":
        await update.message.reply_text("Выберите период:", reply_markup=kb_reports_period())
        return REPORTS_PERIOD
    if text == "🧭 По параметрам":
        await update.message.reply_text("Выберите параметр:", reply_markup=kb_reports_filters())
        return REPORTS_FILTERS
    if text == "🔙 Назад":
        from core.refuel_bot.keyboards.main_keyboard import MainKeyboard
        user = getattr(context, "user", None)
        kb = await MainKeyboard.get_for_user(user)
        await update.message.reply_text("Возвращаю в меню.", reply_markup=kb)
        return ConversationHandler.END
    if text == "❌ Отмена":
        await update.message.reply_text("Отменено.")
        return ConversationHandler.END
    await update.message.reply_text("Выберите вариант из меню.")
    return REPORTS_ROOT


# Периоды
async def reports_period_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    today = date.today()
    if text == "📅 Сегодня":
        start = end = today
    elif text == "📅 Вчера":
        start = end = today - timedelta(days=1)
    elif text == "📅 Неделя":
        start, end = today - timedelta(days=7), today
    elif text == "📅 Месяц":
        start, end = today - timedelta(days=30), today
    elif text == "📅 Произвольная дата":
        await update.message.reply_text("Введите период в формате ДД.ММ.ГГГГ–ДД.ММ.ГГГГ (через дефис):")
        return PERIOD_FREE_INPUT
    elif text == "🔙 Назад":
        await update.message.reply_text("Раздел отчётов:", reply_markup=kb_reports_root())
        return REPORTS_ROOT
    elif text == "❌ Отмена":
        # Возвращаем главное меню
        from core.refuel_bot.keyboards.main_keyboard import MainKeyboard
        user = getattr(context, "user", None)
        kb = await MainKeyboard.get_for_user(user)
        await update.message.reply_text("Отменено.", reply_markup=kb)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Выберите период из меню.", reply_markup=kb_reports_period())
        return REPORTS_PERIOD

    text = await aggregate_period_text(start, end)
    await update.message.reply_text(text)
    # Возвращаем клавиатуру периодов, остаёмся в этом же state
    await update.message.reply_text("Выберите период:", reply_markup=kb_reports_period())
    return REPORTS_PERIOD


# Ввод произвольного периода
async def period_free_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.message.text or "").strip()
    try:
        left, right = [p.strip() for p in raw.replace("—", "-").split("-", 1)]
        start = datetime.strptime(left, "%d.%m.%Y").date()
        end = datetime.strptime(right, "%d.%m.%Y").date()
    except Exception:
        await update.message.reply_text("Неверный формат. Пример: 01.10.2025-31.10.2025. Попробуйте ещё раз:")
        return PERIOD_FREE_INPUT

    text = await aggregate_period_text(start, end)
    await update.message.reply_text(text)
    # Назад к периодам
    await update.message.reply_text("Выберите период:", reply_markup=kb_reports_period())
    return REPORTS_PERIOD


# Фильтры — выбор
async def reports_filters_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text == "🚗 По машине":
        await update.message.reply_text("Введите госномер автомобиля (например: А001АА66):")
        return CAR_INPUT
    if text == "🗺️ По региону":
        await update.message.reply_text("Введите название региона (например: Екатеринбург):")
        return REGION_INPUT
    if text == "📍 По зоне":
        await update.message.reply_text("Введите название или код зоны (например: Урал или URAL):")
        return ZONE_INPUT
    if text == "👤 По заправщику":
        await update.message.reply_text("Введите Telegram ID, @username или часть ФИО:")
        return EMPLOYEE_INPUT
    if text == "🔙 Назад":
        await update.message.reply_text("Раздел отчётов:", reply_markup=kb_reports_root())
        return REPORTS_ROOT
    if text == "❌ Отмена":
        from core.refuel_bot.keyboards.main_keyboard import MainKeyboard
        user = getattr(context, "user", None)
        kb = await MainKeyboard.get_for_user(user)
        await update.message.reply_text("Отменено.", reply_markup=kb)
        return ConversationHandler.END

    await update.message.reply_text("Выберите вариант из меню.", reply_markup=kb_reports_filters())
    return REPORTS_FILTERS


# Фильтры — ввод параметров
async def reports_car_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = normalize_plate_input(update.message.text)
    if plate is None or not is_valid_plate(plate):
        await update.message.reply_text("Неверный формат. Попробуйте ещё раз:")
        return CAR_INPUT
    car, text = await aggregate_car_text(plate)
    await update.message.reply_text(text)
    await update.message.reply_text("Выберите параметр:", reply_markup=kb_reports_filters())
    return REPORTS_FILTERS


async def reports_region_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    region, text = await aggregate_region_text((update.message.text or "").strip())
    await update.message.reply_text(text)
    await update.message.reply_text("Выберите параметр:", reply_markup=kb_reports_filters())
    return REPORTS_FILTERS


async def reports_zone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zone, text = await aggregate_zone_text((update.message.text or "").strip())
    await update.message.reply_text(text)
    await update.message.reply_text("Выберите параметр:", reply_markup=kb_reports_filters())
    return REPORTS_FILTERS


async def reports_employee_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, text = await aggregate_employee_text((update.message.text or "").strip())
    await update.message.reply_text(text)
    await update.message.reply_text("Выберите параметр:", reply_markup=kb_reports_filters())
    return REPORTS_FILTERS


# Обработчик отмены
async def cancel_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from core.refuel_bot.keyboards.main_keyboard import MainKeyboard
    user = getattr(context, "user", None)
    kb = await MainKeyboard.get_for_user(user)
    await update.message.reply_text("Отменено.", reply_markup=kb)
    return ConversationHandler.END


# Собираем Conversation под «📊 Отчёты»
reports_menu_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📊 Отчёты$"), open_reports_menu)],
    states={
        REPORTS_ROOT: [
            MessageHandler(filters.Regex("^🔙 Назад$"), reports_root_router),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_reports),
            MessageHandler(filters.TEXT & ~filters.COMMAND, reports_root_router),
        ],
        REPORTS_PERIOD: [
            MessageHandler(filters.Regex("^🔙 Назад$"), reports_period_router),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_reports),
            MessageHandler(filters.TEXT & ~filters.COMMAND, reports_period_router),
        ],
        PERIOD_FREE_INPUT: [
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_reports),
            MessageHandler(filters.TEXT & ~filters.COMMAND, period_free_input),
        ],
        REPORTS_FILTERS: [
            MessageHandler(filters.Regex("^🔙 Назад$"), reports_filters_router),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_reports),
            MessageHandler(filters.TEXT & ~filters.COMMAND, reports_filters_router),
        ],
        CAR_INPUT: [
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_reports),
            MessageHandler(filters.TEXT & ~filters.COMMAND, reports_car_input),
        ],
        REGION_INPUT: [
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_reports),
            MessageHandler(filters.TEXT & ~filters.COMMAND, reports_region_input),
        ],
        ZONE_INPUT: [
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_reports),
            MessageHandler(filters.TEXT & ~filters.COMMAND, reports_zone_input),
        ],
        EMPLOYEE_INPUT: [
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_reports),
            MessageHandler(filters.TEXT & ~filters.COMMAND, reports_employee_input),
        ],
    },
    fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), cancel_reports)],
    per_user=True,
    per_chat=True,
    per_message=False,
    name="reports_menu_conversation"
)
