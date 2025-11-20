# core/bot/keyboards/refuel_method_keyboard.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class RefuelMethodKeyboard:
    def get_inline(self):
        keyboard = [
            [
                [
                    InlineKeyboardButton("ТГ-бот", callback_data="refuel_method:tg_bot"),
                    InlineKeyboardButton("Карта", callback_data="refuel_method:fuel_card")
                ],
                InlineKeyboardButton("Топливозаправщик", callback_data="refuel_method:truck")
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
