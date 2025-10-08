from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, WebAppInfo
import os
from .ui_labels import (
    BTN_TARIFF,
    BTN_PROFILE,
    BTN_TRIAL,
    BTN_INVITE,
    BTN_GUIDE,
    BTN_SUPPORT,
    BTN_BACK,
    BTN_MY_CONFIGS,
    BTN_ACTIVATE_DAYS,
    BTN_SETUP_PHONE,
    BTN_SETUP_PC,
    BTN_ADD_SUB_WEBAPP,
    BTN_COPY_SUB,
    tariff_1m_label,
    tariff_3m_label,
)


def create_keyboard():
    kb_list = [
        [KeyboardButton(text=BTN_TARIFF), KeyboardButton(text=BTN_PROFILE)],
        [KeyboardButton(text=BTN_TRIAL)],
        [KeyboardButton(text=BTN_INVITE), KeyboardButton(text=BTN_GUIDE)]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)
    return keyboard

def create_admin_keyboard():
    """Создает клавиатуру для администратора."""
    kb_list = [
        [KeyboardButton(text=BTN_TARIFF), KeyboardButton(text=BTN_PROFILE)],
        [KeyboardButton(text=BTN_TRIAL)],
        [KeyboardButton(text=BTN_INVITE), KeyboardButton(text=BTN_GUIDE)],
        [KeyboardButton(text="🔧 Админ панель")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)
    return keyboard


def create_server_keyboard():
    # Read ordered list of servers from env, e.g., "fi,nl,de,us"
    order_env = os.getenv("SERVER_ORDER", "fi,ge").strip()
    server_codes = [s.strip().lower() for s in order_env.split(',') if s.strip()]
    if not server_codes:
        server_codes = ["fi", "ge"]

    # Simple mapping of known titles/flags; unknown codes will be shown uppercased without flag
    titles = {
        "fi": "Финляндия",
        "nl": "Нидерланды",
        "de": "Германия",
        "ge": "Германия",
        "us": "США",
        "pl": "Польша",
        "se": "Швеция",
        "fr": "Франция",
        "gb": "Великобритания",
        "uk": "Великобритания",
        "tr": "Турция",
    }
    flags = {
        "fi": "🇫🇮",
        "nl": "🇳🇱",
        "de": "🇩🇪",
        "ge": "🇩🇪",
        "us": "🇺🇸",
        "pl": "🇵🇱",
        "se": "🇸🇪",
        "fr": "🇫🇷",
        "gb": "🇬🇧",
        "uk": "🇬🇧",
        "tr": "🇹🇷",
    }

    rows: list[list[InlineKeyboardButton]] = []
    for code in server_codes:
        title = titles.get(code, code.upper())
        flag = flags.get(code, "")
        text = f"{title} {flag}".strip()
        rows.append([InlineKeyboardButton(text=text, callback_data=f"server_{code}")])

    # Add back button
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def create_tariff_keyboard():
    star_1m = int(os.getenv("PRICE_1M_STAR", "149"))
    star_3m = int(os.getenv("PRICE_3M_STAR", "299"))
    rub_1m = int(os.getenv("PRICE_1M_RUB", "149"))
    rub_3m = int(os.getenv("PRICE_3M_RUB", "299"))

    kb_list = [
        [InlineKeyboardButton(text=tariff_1m_label(star_1m, rub_1m), callback_data="plan_1m")],
        [InlineKeyboardButton(text=tariff_3m_label(star_3m, rub_3m), callback_data="plan_3m")],
        [InlineKeyboardButton(text=BTN_BACK, callback_data="back")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_list)
    return keyboard



def create_payment_method_keyboard(star_amount: int, rub_amount: int):
    kb_list = [
        [InlineKeyboardButton(text=f"Telegram Stars · {star_amount} ⭐", callback_data="pay_star")],
        [InlineKeyboardButton(text=f"Картой (ЮKassa) · {rub_amount} ₽", callback_data="pay_cash")],
        [InlineKeyboardButton(text=BTN_BACK, callback_data="back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def create_settings_keyboard():
    kb_list = [
        [KeyboardButton(text=BTN_SETUP_PHONE), KeyboardButton(text=BTN_SETUP_PC)],
        [KeyboardButton(text=BTN_SUPPORT)],
        [KeyboardButton(text=BTN_BACK)]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)
    return keyboard



def create_profile_keyboard():
    kb_list = [
        [KeyboardButton(text=BTN_MY_CONFIGS)],
        [KeyboardButton(text=BTN_ACTIVATE_DAYS)],
        [KeyboardButton(text=BTN_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)



def create_activate_balance_inline(balance_days: int):
    text = f"Активировать: {balance_days} дн." if balance_days > 0 else "Обновить"
    kb_list = [
        [InlineKeyboardButton(text=text, callback_data="activate_balance")],
        [InlineKeyboardButton(text=BTN_BACK, callback_data="back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def create_settings_inline(prefs: dict, fav_server: str | None):
    kb_list = [[InlineKeyboardButton(text=BTN_BACK, callback_data="back")]]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def create_pref_server_inline(current: str | None):
    kb_list = [[InlineKeyboardButton(text=BTN_BACK, callback_data="back")]]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)

