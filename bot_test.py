# bot_test.py
import asyncio
import logging
from django.conf import settings
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Простая команда /start для теста
async def test_start(update: Update, context):
    logger.info(f"Received /start from {update.effective_user.id}")
    await update.message.reply_text("Bot is alive!")


async def main():
    token = settings.TELEGRAM.get("TOKEN")
    if not token:
        logger.error("TELEGRAM TOKEN is not set!")
        return

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", test_start))
    logger.info("Test bot built. Running polling for 5 seconds...")

    # Запускаем polling на короткое время
    async with app:
        await asyncio.wait_for(app.updater.start_polling(), timeout=5)
        logger.info("Polling started successfully")


if __name__ == "__main__":
    asyncio.run(main())
