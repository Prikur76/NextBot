# bot_test.py
import logging
from django.conf import settings
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_start(update: Update, context):
    logger.info(f"Received /start from {update.effective_user.id}")
    await update.message.reply_text("Bot is alive!")


def main():
    token = settings.TELEGRAM.get("TOKEN")
    if not token:
        logger.error("TELEGRAM TOKEN is not set!")
        return

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", test_start))

    logger.info("Test bot built. Starting polling for 10 seconds...")
    
    # Метод run_polling корректно инициализирует HTTPXRequest и все асинхронные компоненты
    app.run_polling(timeout=10)  # остановится автоматически через 10 сек


if __name__ == "__main__":
    main()