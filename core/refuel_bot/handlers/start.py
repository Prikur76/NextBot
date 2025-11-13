# core/bot/handlers/start.py
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, ContextTypes, filters

from core.refuel_bot.keyboards.main_keyboard import MainKeyboard


# === Старт ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)

    if not user:
        await update.message.reply_text(
            "⛔ Вы не зарегистрированы в системе. Обратитесь к администратору.",
        )
        return

    text = (
        f"Здравствуйте, {user.first_name or user.username}!\n\n"
        "Вы можете:\n• Ввести заправку\n• Посмотреть историю и отчёты"
    )
    kb = await MainKeyboard.get_for_user(user)
    await update.message.reply_text(text, reply_markup=kb)
    

start_handler = CommandHandler("start", start)


# === Помощь ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    if not user:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    text = (
        "🆘 Помощь\n\n"
        "Доступные действия:\n"
        "• ⛽ Добавить — пошаговый ввод заправки (госномер → литры → способ).\n"
        "• 📊 Отчёты — отчёты по периодам и параметрам (для менеджеров/админов).\n\n"
        "Команды:\n"
        "• /start — главное меню\n"
        "• /help — показать эту подсказку\n"
        "Подсказки:\n"
        "• Госномер: кириллица, без пробелов/дефисов (АА12345, А123ВС45, А123ВС456).\n"
        "• Литры: с точкой или запятой (например 45.5).\n"
        "• «🔙 Назад» возвращают на предыдущий шаг"
        "• «❌ Отмена» прерывает шаг и возвращает в главное меню."
    )
    kb = await MainKeyboard.get_for_user(user)
    await update.message.reply_text(text, reply_markup=kb)


help_handler = CommandHandler("help", help_command)
help_message_handler = MessageHandler(filters.Regex(r"^❓ Помощь$"), help_command)