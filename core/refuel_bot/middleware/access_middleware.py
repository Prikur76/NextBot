# core/bot/middleware/access_middleware.py
import logging
from functools import lru_cache

from asgiref.sync import sync_to_async
from telegram import Update
from telegram.ext import ContextTypes

from core.models import User


logger = logging.getLogger(__name__)


def _fetch_user_sync(telegram_id: int):
    """
    Синхронная функция для безопасного выполнения ORM внутри sync thread.
    ВАЖНО: весь ORM-код должен выполняться только здесь.
    """
    return (
        User.objects
        .select_related("zone", "region")
        .filter(telegram_id=telegram_id, is_active=True)
        .first()
    )


# Небольшой LRU-кэш для защиты от спам-запросов одного пользователя
# Сбрасывается автоматически при Шардинге, деплое, рестарте
@lru_cache(maxsize=2048)
def _cached_sync_fetch(telegram_id: int):
    return _fetch_user_sync(telegram_id)


async def access_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Подставляет Django User в context.user, если telegram_id соответствует активному пользователю.
    Выполняется для каждого Telegram update как ранний TypeHandler.
    """

    # Инициализация поля
    try:
        context.user = None
    except Exception:
        context.user_data["_django_user"] = None

    tg_user = getattr(update, "effective_user", None)
    if not tg_user:
        return

    telegram_id = tg_user.id

    # Обёртка sync_to_async вызывается *на саму sync-функцию*, а не на лямбду.
    fetch_user_async = sync_to_async(_cached_sync_fetch, thread_sensitive=True)

    try:
        user = await fetch_user_async(telegram_id)

        try:
            context.user = user
        except Exception:
            context.user_data["_django_user"] = user

    except Exception:
        logger.exception("❌ Ошибка получения User для telegram_id=%s", telegram_id)

        # fallback
        try:
            context.user = None
        except Exception:
            context.user_data["_django_user"] = None
