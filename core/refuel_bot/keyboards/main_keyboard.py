# core/bot/keyboards/main_keyboard.py
from telegram import ReplyKeyboardMarkup
from asgiref.sync import sync_to_async


class MainKeyboard:
    """Reply keyboard used in main menu with role-based layout."""

    @staticmethod
    @sync_to_async
    def _get_role(user):
        if user is None:
            return 'anon'
        if user.is_superuser or user.groups.filter(name="Администратор").exists():
            return 'admin'
        if user.groups.filter(name="Менеджер").exists():
            return 'manager'
        if user.groups.filter(name="Заправщик").exists():
            return 'fueler'
        return 'other'

    @staticmethod
    async def get_for_user(user=None):
        role = await MainKeyboard._get_role(user) if user else 'anon'

        if role == 'fueler':
            keyboard = [
                ["⛽ Добавить"],
                ["❓ Помощь"],
            ]
        elif role in ('manager', 'admin'):
            keyboard = [
                ["⛽ Добавить"], 
                ["📊 Отчёты", "❓ Помощь"]
            ]
        else:
            keyboard = [["❓ Помощь"]]

        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
