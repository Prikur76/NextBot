# core/bot/handlers/fuel_input.py
from decimal import Decimal, InvalidOperation
from asgiref.sync import sync_to_async
from django.utils import timezone as dj_tz
from telegram import Update
from telegram.ext import (
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

from core.refuel_bot.keyboards.cancel_keyboard import CancelKeyboard
from core.refuel_bot.keyboards.main_keyboard import MainKeyboard
from core.refuel_bot.keyboards.refuel_method_keyboard import RefuelMethodKeyboard
from core.refuel_bot.utils.validate_state_plate import is_valid_plate, normalize_plate_input
from core.models import Car, FuelRecord


# States
WAITING_CAR, WAITING_LITERS, WAITING_REFUEL_METHOD = range(3)


cancel_kb = CancelKeyboard()
refuel_kb = RefuelMethodKeyboard()
main_kb = MainKeyboard()


# --- DB helpers (все ORM здесь, чтобы не вызывать их напрямую из async) ---
@sync_to_async
def find_car_by_state_number(state_number: str):
    # при необходимости приведите сохранённые номера в БД к тому же формату
    return Car.objects.filter(state_number__iexact=state_number, is_active=True).first()


@sync_to_async
def get_car_by_id(cid: int):
    return Car.objects.filter(id=cid).first()


@sync_to_async
def create_fuel_record(*, car, employee, liters: Decimal, fuel_type: str, source: str, filled_at, approved: bool):
    return FuelRecord.objects.create(
        car=car,
        employee=employee,
        liters=liters,
        fuel_type=fuel_type,
        source=source,
        filled_at=filled_at,
        approved=approved,
    )


@sync_to_async
def user_in_group(user, group_name: str) -> bool:
    return user and user.groups.filter(name=group_name).exists()


# Helper for state stack to implement "Back" functionality
def push_state(context: ContextTypes.DEFAULT_TYPE, state):
    stack = context.user_data.setdefault("_state_stack", [])
    stack.append(state)


def pop_state(context: ContextTypes.DEFAULT_TYPE):
    stack = context.user_data.get("_state_stack", [])
    if stack:
        stack.pop()
    if stack:
        return stack.pop()
    return None


# --- Хелперы для удаления сообщений бота ---
async def delete_last_bot_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mid = context.user_data.pop("last_bot_mid", None)
    if not mid:
        return
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mid)
    except Exception:
        # Игнорируем, если уже удалено/не доступно
        pass

async def try_delete_user_message(update: Update):
    # В личных чатах Telegram не даёт боту удалять сообщения пользователя — это нормально.
    try:
        if update and update.message:
            await update.message.delete()
    except Exception:
        pass

def remember_bot_message(context: ContextTypes.DEFAULT_TYPE, msg):
    if msg:
        context.user_data["last_bot_mid"] = msg.message_id


# --- Handlers ---
async def start_fuel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    if not user:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return ConversationHandler.END

    context.user_data["_state_stack"] = []
    push_state(context, "ENTRY")
    msg = await update.message.reply_text(
        "🚗 Отлично! Введите госномер автомобиля (например: A123BC77):",
        reply_markup=cancel_kb.get()
    )
    remember_bot_message(context, msg)
    return WAITING_CAR


async def process_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text or ""
    plate = normalize_plate_input(raw_text)

    # Валидируем по маскам
    if not is_valid_plate(plate):
        msg = await update.message.reply_text(
            "Неверный формат госномера.\n"
            "Допустимые примеры: АА12345, А123ВС45, А123ВС456.\n"
            f"Используйте только кирилицу и цифры.",
            reply_markup=cancel_kb.get()
        )
        remember_bot_message(context, msg)
        return WAITING_CAR

    # Ищем авто строго по госномеру
    car = await find_car_by_state_number(plate)
    if not car:
        msg = await update.message.reply_text(
            "Автомобиль с таким госномером не найден или не активен. Попробуйте ещё раз:",
            reply_markup=cancel_kb.get()
        )
        remember_bot_message(context, msg)
        return WAITING_CAR

    context.user_data["car_id"] = car.id
    context.user_data["car_display"] = f"{car.model or '—'} ({car.state_number})"
    push_state(context, WAITING_CAR)

    msg  = await update.message.reply_text(
        f"Автомобиль найден: {context.user_data['car_display']}\n\nВведите количество литров (например: 45.5):",
        reply_markup=cancel_kb.get()
    )
    remember_bot_message(context, msg)
    return WAITING_LITERS


async def process_liters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        liters = Decimal(text)
        if liters <= 0 or liters > 330:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        msg = await update.message.reply_text("Неверное количество. Введите число (0.1 — 330):", reply_markup=cancel_kb.get())
        remember_bot_message(context, msg)
        return WAITING_LITERS

    context.user_data["liters"] = liters
    push_state(context, WAITING_LITERS)

    msg = await update.message.reply_text(
        f"Вы указали {liters.quantize(Decimal('0.01'))} л. Выберите способ заправки:",
        reply_markup=refuel_kb.get_inline()
    )
    remember_bot_message(context, msg)
    return WAITING_REFUEL_METHOD


async def process_refuel_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)

    # Определяем источник данных: callback или текст
    if update.callback_query:
        await update.callback_query.answer()
        data = update.callback_query.data or ""
        is_cb = True
    else:
        data = (update.message.text or "").strip()
        is_cb = False

    data_low = data.lower()

    # ----- Отмена -----
    if (is_cb and data.endswith(":cancel")) or (not is_cb and data == "❌ Отмена"):
        # Убираем сообщение с экрана
        if is_cb:
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass
        else:
            await try_delete_user_message(update)
            await delete_last_bot_message(update, context)

        context.user_data.clear()
        await update.effective_chat.send_message(
            "Ввод отменён.",
            reply_markup=(await main_kb.get_for_user(user))
        )
        return ConversationHandler.END

    # ----- Назад -----
    if (is_cb and data.endswith(":back")) or (not is_cb and data == "🔙 Назад"):
        if is_cb:
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass
        else:
            await try_delete_user_message(update)
            await delete_last_bot_message(update, context)

        prev = pop_state(context)

        if prev == WAITING_CAR:
            msg = await update.effective_chat.send_message(
                "Возврат к вводу госномера. Введите госномер:",
                reply_markup=cancel_kb.get()
            )
            remember_bot_message(context, msg)
            return WAITING_CAR

        if prev == WAITING_LITERS:
            msg = await update.effective_chat.send_message(
                "Возврат к вводу литров. Введите количество литров:",
                reply_markup=cancel_kb.get()
            )
            remember_bot_message(context, msg)
            return WAITING_LITERS

        await update.effective_chat.send_message(
            "Возврат в главное меню.",
            reply_markup=(await main_kb.get_for_user(user))
        )
        return ConversationHandler.END

    # ----- Выбор метода -----
    # Маппинг на choices модели: 'tg-bot', 'card', 'truck'
    if (is_cb and data == "refuel_method:tg_bot") or (not is_cb and data_low in {"тг-бот", "через бота (ввести вручную)", "тг бот", "бот"}):
        method, method_name = "TGBOT", "Телеграм-бот"
    elif (is_cb and data == "refuel_method:fuel_card") or (not is_cb and data_low == "топливная карта"):
        method, method_name = "CARD", "Топливная карта"        
    elif (is_cb and data == "refuel_method:truck") or (not is_cb and data_low == "топливозаправщик"):
        method, method_name = "TRUCK", "Топливозаправщик"
    else:
        # Некорректный ввод — повторно показываем клавиатуру выбора
        if is_cb:
            await update.callback_query.message.reply_text(
                "Выберите корректный способ.",
                reply_markup=refuel_kb.get_inline()
            )
        else:
            msg = await update.message.reply_text(
                "Выберите корректный способ.",
                reply_markup=refuel_kb.get_inline()
            )
            remember_bot_message(context, msg)
        return WAITING_REFUEL_METHOD

    # ----- Проверка данных контекста -----
    car_id = context.user_data.get("car_id")
    liters = context.user_data.get("liters")
    if not car_id or liters is None:
        # Чистим экран от инлайн/служебных сообщений
        if is_cb:
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass
        else:
            await delete_last_bot_message(update, context)

        context.user_data.clear()
        await update.effective_chat.send_message(
            "Ошибка данных — начните заново.",
            reply_markup=(await main_kb.get_for_user(user))
        )
        return ConversationHandler.END

    # ----- Создание записи -----
    car = await get_car_by_id(car_id)
    await create_fuel_record(
        car=car,
        employee=user,
        liters=liters,  # Decimal
        fuel_type="GASOLINE",
        source=method,
        filled_at=dj_tz.now(),
        approved=False
    )

    # ----- Ответ об успехе -----
    success_text = (
        f"✅ Заправка сохранена: {context.user_data.get('car_display', '—')} — "
        f"{liters.quantize(Decimal('0.01'))} л (метод: {method_name})"
    )
    if is_cb:
        # Аккуратно заменяем инлайн-сообщение на результат
        try:
            await update.callback_query.edit_message_text(success_text)
        except Exception:
            await update.effective_chat.send_message(success_text)
        await update.effective_chat.send_message(
            "Возвращаю в меню.",
            reply_markup=(await main_kb.get_for_user(user))
        )
    else:
        # Уберём последнюю подсказку (если была сохранена) и ответим
        await delete_last_bot_message(update, context)
        await update.effective_chat.send_message(
            success_text,
            reply_markup=(await main_kb.get_for_user(user))
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    # Сначала пробуем удалить сообщение пользователя "Отмена"
    await try_delete_user_message(update)
    # Убираем последнее служебное сообщение бота (подсказку/меню)
    await delete_last_bot_message(update, context)

    context.user_data.clear()
    await update.effective_chat.send_message(
        "Операция отменена.",
        reply_markup=(await main_kb.get_for_user(user))
    )
    return ConversationHandler.END


async def back_from_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    await try_delete_user_message(update)
    await delete_last_bot_message(update, context)

    context.user_data.clear()
    await update.effective_chat.send_message(
        "Возвращаю в меню.",
        reply_markup=(await main_kb.get_for_user(user))
    )
    return ConversationHandler.END


async def back_from_liters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await try_delete_user_message(update)
    await delete_last_bot_message(update, context)

    msg = await update.effective_chat.send_message(
        "Возврат к вводу госномера. Введите госномер:",
        reply_markup=cancel_kb.get()
    )
    remember_bot_message(context, msg)
    return WAITING_CAR


# conversation handler (добавьте обработчик "Назад" при желании в каждый state)
fuel_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^⛽ Добавить$"), start_fuel_input)],
    states={
        WAITING_CAR: [
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
            MessageHandler(filters.Regex("^🔙 Назад$"), back_from_car),
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_car_number)
        ],
        WAITING_LITERS: [
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
            MessageHandler(filters.Regex("^🔙 Назад$"), back_from_liters),
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_liters)
        ],
        WAITING_REFUEL_METHOD: [
            CallbackQueryHandler(process_refuel_method, pattern="^refuel_method:"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_refuel_method)
        ]
    },
    fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), cancel)],
    per_user=True,
    per_chat=True,
    per_message=False,
    name="fuel_conversation"
)


# /fuel <код|госномер> <литры> <способ>
async def fuel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    if not user or not await user_in_group(user, "Заправщик"):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Использование: /fuel <госномер> <литры> <способ>")
        return

    state_plate, liters_text, method = args
    try:
        liters = Decimal(liters_text.replace(",", "."))
        if liters <= 0 or liters > 2000:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Неверный формат литров.")
        return

    car = await find_car_by_state_or_code(state_plate)
    if not car:
        await update.message.reply_text("Автомобиль не найден.")
        return

    await create_fuel_record(
        car=car,
        employee=user,
        liters=liters,
        fuel_type=car.fuel_type,
        source=method if method else "tg-bot",
        filled_at=dj_tz.now(),
        approved=False,
    )
    await update.message.reply_text(f"Заправка сохранена: {car.state_number} — {liters.quantize(Decimal('0.01'))} л (метод: {method})")

fuel_command_handler = CommandHandler("fuel", fuel_command)
