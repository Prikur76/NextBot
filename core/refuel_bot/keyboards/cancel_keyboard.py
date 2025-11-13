# core/bot/keyboards/cancel_keyboard.py
from telegram import ReplyKeyboardMarkup


class CancelKeyboard:
    def get(self):
        return ReplyKeyboardMarkup(
            [["🔙 Назад", "❌ Отмена"]], 
            resize_keyboard=True, 
            one_time_keyboard=False
        )
