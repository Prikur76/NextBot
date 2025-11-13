import logging

from asgiref.sync import sync_to_async
from core.models import SystemLog


logger = logging.getLogger("nextbot.custom")


def log_action(user=None, action="info", details="", ip_address=None):
    """Создание записи в БД + стандартный лог."""
    log_record = SystemLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        details=details,
        ip_address=ip_address,
    )
    
    # Пишем также в общий лог
    username = user.username if user and user.is_authenticated else "SYSTEM"
    ip_info = f" [{ip_address}]" if ip_address else ""
    logger.info(f"{username}{ip_info} — {action}: {details}")
    
    return log_record


@sync_to_async
def log_command_action(action: str, details: str, user=None):
    """
    Безопасное логирование для management команд
    """
    SystemLog.objects.create(
        user=user,
        action=action,
        details=details,
        ip_address=None  # В командах нет IP
    )


async def log_sync_success(message: str, stats: dict):
    """Логирует успешную синхронизацию"""
    await log_command_action("info", message)


async def log_sync_failure(error: str):
    """Логирует ошибку синхронизации"""
    await log_command_action("error", f"Ошибка синхронизации автомобилей: {error}")
