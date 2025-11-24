# core/refuel_bot/keyboards/fuel_type_keyboard.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class FuelTypeKeyboard:
    def get_inline(self):
        keyboard = [
            [
                InlineKeyboardButton("Бензин", callback_data="fuel_type:GASOLINE"),
                InlineKeyboardButton("Дизель", callback_data="fuel_type:DIESEL"),
            ],
            [
                InlineKeyboardButton("🔙 Назад", callback_data="fuel_type:back"),
                InlineKeyboardButton("❌ Отмена", callback_data="fuel_type:cancel"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)