# core/bot/middleware/access_middleware.py
import logging
from typing import Dict, Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone as dj_tz
from telegram import Update
from telegram.ext import ContextTypes

from core.models import User


logger = logging.getLogger(__name__)

# Ключ кэша: bot_user:<telegram_id>
CACHE_KEY_PREFIX = "bot_user:"
# Время жизни кэша — 15 минут (настройте под себя)
CACHE_TTL = 60 * 15  # 15 минут


def _fetch_user_data_sync(telegram_id: int) -> Dict[str, Any] | None:
    """
    Синхронная функция: загружает данные пользователя и его группы.
    Возвращает словарь, безопасный для кэширования.
    """
    try:
        user = (
            User.objects
            .select_related("zone", "region")
            .prefetch_related("groups")
            .filter(telegram_id=telegram_id, is_active=True)
            .first()
        )
        if not user:
            return None

        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "zone": user.zone,
            "region": user.region,
            "group_names": list(user.groups.values_list("name", flat=True)),
            "fetched_at": dj_tz.now().isoformat(),
        }
    except Exception as e:
        logger.exception("Ошибка при загрузке пользователя telegram_id=%s", telegram_id)
        return None


async def access_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Подставляет Django User в context.user, если telegram_id соответствует активному пользователю.
    Использует кэширование через django.core.cache для производительности.
    Выполняется как TypeHandler на каждом update.
    """
    # Инициализация поля user
    context.user = None

    tg_user = getattr(update, "effective_user", None)
    if not tg_user:
        return

    telegram_id = tg_user.id
    cache_key = f"{CACHE_KEY_PREFIX}{telegram_id}"

    # 1. Попробуем получить из кэша
    user_data = cache.get(cache_key)

    # 2. Если нет в кэше — загружаем из БД
    if user_data is None:
        user_data = await sync_to_async(_fetch_user_data_sync, thread_sensitive=True)(telegram_id)

        if user_data is None:
            logger.warning("Пользователь не найден или неактивен: telegram_id=%s", telegram_id)
            return

        # Сохраняем в кэш только если пользователь найден
        cache.set(cache_key, user_data, timeout=CACHE_TTL)

    # 3. Создаём "лёгкий" объект User (без связи с БД), чтобы не передавать ORM-объект
    # Это важно, потому что ORM-объекты нельзя передавать между потоками
    class MockUser:
        def __init__(self, data):
            self.id = data["id"]
            self.telegram_id = data["telegram_id"]
            self.username = data["username"]
            self.first_name = data["first_name"]
            self.last_name = data["last_name"]
            self.is_active = data["is_active"]
            self.zone_id = data["zone_id"]
            self.region_id = data["region_id"]
            self.group_names = data["group_names"]

        def get_full_name(self):
            return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.username

        def groups_filter(self, name: str) -> bool:
            return name in self.group_names

    # 4. Привязываем к контексту
    try:
        context.user = MockUser(user_data)
    except Exception:
        # Резервный вариант, если context не позволяет установить user
        context.user_data["_django_user"] = MockUser(user_data)

    logger.debug("Пользователь загружен в контекст: %s (%s)", context.user.get_full_name(), telegram_id)
