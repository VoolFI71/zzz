from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, LabeledPrice, PreCheckoutQuery, Message, CallbackQuery
import os


def create_keyboard():
    kb_list = [
        [KeyboardButton(text="Выбрать тариф"), KeyboardButton(text="Личный кабинет")],
        [KeyboardButton(text="🎁 Пробная 3 дня")],
        [KeyboardButton(text="Пригласить"), KeyboardButton(text="Инструкция⚙️")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)
    return keyboard


def create_server_keyboard():
    kb_list = [
        [InlineKeyboardButton(text="Финляндия 🇫🇮", callback_data="server_fi")],
        [InlineKeyboardButton(text="Нидерланды 🇳🇱", callback_data="server_nl")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)



def create_tariff_keyboard():
    star_1m = int(os.getenv("PRICE_1M_STAR", "149"))
    star_3m = int(os.getenv("PRICE_3M_STAR", "299"))
    rub_1m = int(os.getenv("PRICE_1M_RUB", "149"))
    rub_3m = int(os.getenv("PRICE_3M_RUB", "329"))

    kb_list = [
        [InlineKeyboardButton(text=f"📅 1 месяц — {star_1m} ⭐ / {rub_1m} ₽", callback_data="plan_1m")],
        [InlineKeyboardButton(text=f"📆 3 месяца — {star_3m} ⭐ / {rub_3m} ₽", callback_data="plan_3m")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_list)
    return keyboard



def create_payment_method_keyboard(star_amount: int, rub_amount: int):
    kb_list = [
        [InlineKeyboardButton(text=f"Оплатить звёздами — {star_amount} ⭐", callback_data="pay_star")],
        [InlineKeyboardButton(text=f"Оплатить YooKassa — {rub_amount} ₽", callback_data="pay_cash")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def create_settings_keyboard():
    kb_list = [
        [KeyboardButton(text="Установка на Телефон"), KeyboardButton(text="Установка на PC")],
        [KeyboardButton(text="Назад")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)
    return keyboard



def create_profile_keyboard():
    kb_list = [
        [KeyboardButton(text="Мои конфиги")],
        [KeyboardButton(text="Активировать дни")],
        [KeyboardButton(text="Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)



def create_activate_balance_inline(balance_days: int):
    text = f"Активировать {balance_days} дн." if balance_days > 0 else "Обновить"
    kb_list = [
        [InlineKeyboardButton(text=text, callback_data="activate_balance")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)