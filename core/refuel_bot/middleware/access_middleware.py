# core/bot/middleware/access_middleware.py
import logging

from asgiref.sync import sync_to_async
from telegram import Update
from telegram.ext import ContextTypes

from core.models import User


logger = logging.getLogger(__name__)


async def access_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Подставляет Django User в context.user, если telegram_id соответствует активному пользователю.
    Выполняется для каждого апдейта как ранний TypeHandler.
    """
    # Значение по умолчанию
    try:
        context.user = None
    except Exception:
        # На случай, если у CallbackContext запрещены новые атрибуты
        context.user_data["_django_user"] = None

    tg_user = getattr(update, "effective_user", None)
    if tg_user is None:
        return

    try:
        get_user = sync_to_async(
            lambda: (
                User.objects
                .select_related("zone", "region")
                .filter(telegram_id=tg_user.id, is_active=True)
                .first()
            ),
            thread_sensitive=True,
        )
        user = await get_user()

        # Пытаемся положить в context.user; если нельзя — в user_data
        try:
            context.user = user
        except Exception:
            context.user_data["_django_user"] = user

    except Exception:
        logger.exception("Не удалось получить User для telegram_id=%s", getattr(tg_user, "id", None))
        try:
            context.user = None
        except Exception:
            context.user_data["_django_user"] = None
