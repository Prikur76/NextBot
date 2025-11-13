# core/bot/main.py
import logging

from django.conf import settings
from telegram import Update
from telegram.ext import ApplicationBuilder, TypeHandler
from telegram.request import HTTPXRequest

from core.refuel_bot.handlers.start import start_handler, help_handler, help_message_handler
from core.refuel_bot.handlers.fuel_input import fuel_conv_handler, fuel_command_handler
from core.refuel_bot.handlers.report import reports_menu_conv_handler
from core.refuel_bot.middleware.access_middleware import access_middleware


logger = logging.getLogger(__name__)


async def error_handler(update: Update, context):
    logger.exception("Unhandled exception in handler", exc_info=context.error)


def build_app():
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in settings")
    
    # Читаем прокси из окружения/настроек (если нужно)
    # Можно использовать HTTPS_PROXY из окружения или свой TELEGRAM_PROXY_URL в .env
    proxy_url = getattr(settings, "TELEGRAM_PROXY_URL", None) or None
    request = HTTPXRequest(
        connect_timeout=20.0,   # увеличить время соединения
        read_timeout=40.0,      # чтение ответа
        write_timeout=20.0,     # отправка запроса
        pool_timeout=5.0,       # ожидание свободного соединения
        proxy=proxy_url         # 'http://host:port' или 'socks5://user:pass@host:port'
    )

    app = ApplicationBuilder().token(token).request(request).build()
    app.add_handler(TypeHandler(Update, access_middleware), group=-1)

    # Команды/кнопки
    app.add_handler(start_handler)
    app.add_handler(help_handler)
    app.add_handler(help_message_handler)

    # Бот-функционал
    app.add_handler(fuel_command_handler)
    app.add_handler(fuel_conv_handler)
    app.add_handler(reports_menu_conv_handler)

    app.add_error_handler(error_handler)

    logger.info("Telegram application built")
    return app


def run_bot():
    app = build_app()
    app.run_polling()

    logger.info("Telegram bot stopped")