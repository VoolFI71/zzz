from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, LabeledPrice, PreCheckoutQuery, Message, CallbackQuery

def create_keyboard():
    kb_list = [
        [KeyboardButton(text="Выбрать тариф"), KeyboardButton(text="Личный кабинет")],
        [KeyboardButton(text="Пригласить"), KeyboardButton(text="Инструкция⚙️")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=True)
    return keyboard

def create_server_keyboard():
    kb_list = [
        [InlineKeyboardButton(text="Финляндия 🇫🇮", callback_data="server_fi")],
        [InlineKeyboardButton(text="Нидерланды 🇳🇱", callback_data="server_nl")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def create_tariff_keyboard():
    kb_list = [
        [InlineKeyboardButton(text="Купить на 1 месяц - 99 Рублей💰", callback_data="buy_1")],
        [InlineKeyboardButton(text="Купить на 3 месяца - 199 Рублей💰", callback_data="buy_2")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]

    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_list)
    return keyboard

def create_settings_keyboard():
    kb_list = [
        [KeyboardButton(text="Установка на Телефон"), KeyboardButton(text="Установка на PC")],
        [KeyboardButton(text="Назад")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=True)
    return keyboard