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
        [InlineKeyboardButton(text="3 дня", callback_data="plan_3d")],
        [InlineKeyboardButton(text="1 месяц", callback_data="plan_1m")],
        [InlineKeyboardButton(text="3 месяца", callback_data="plan_3m")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_list)
    return keyboard


def create_payment_method_keyboard(star_amount: int, rub_amount: int):
    kb_list = [
        [InlineKeyboardButton(text=f"Оплатить звёздами — {star_amount} ⭐", callback_data="pay_star")],
        [InlineKeyboardButton(text=f"Оплатить YooKassa — {rub_amount} ₽", callback_data="pay_cash")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)

def create_settings_keyboard():
    kb_list = [
        [KeyboardButton(text="Установка на Телефон"), KeyboardButton(text="Установка на PC")],
        [KeyboardButton(text="Назад")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=True)
    return keyboard