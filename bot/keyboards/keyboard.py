from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, WebAppInfo
import os


def create_keyboard():
    kb_list = [
        [KeyboardButton(text="📦 Выбрать тариф"), KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="🎁 Пробные 3 дня")],
        [KeyboardButton(text="🤝 Пригласить"), KeyboardButton(text="🛠️ Инструкция")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)
    return keyboard

def create_admin_keyboard():
    """Создает клавиатуру для администратора."""
    kb_list = [
        [KeyboardButton(text="📦 Выбрать тариф"), KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="🎁 Пробные 3 дня")],
        [KeyboardButton(text="🤝 Пригласить"), KeyboardButton(text="🛠️ Инструкция")],
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
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def create_tariff_keyboard():
    star_1m = int(os.getenv("PRICE_1M_STAR", "149"))
    star_3m = int(os.getenv("PRICE_3M_STAR", "299"))
    rub_1m = int(os.getenv("PRICE_1M_RUB", "149"))
    rub_3m = int(os.getenv("PRICE_3M_RUB", "299"))

    kb_list = [
        [InlineKeyboardButton(text=f"1 месяц · {star_1m} ⭐ / {rub_1m} ₽", callback_data="plan_1m")],
        [InlineKeyboardButton(text=f"3 месяца · {star_3m} ⭐ / {rub_3m} ₽", callback_data="plan_3m")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_list)
    return keyboard



def create_payment_method_keyboard(star_amount: int, rub_amount: int):
    kb_list = [
        [InlineKeyboardButton(text=f"Telegram Stars · {star_amount} ⭐", callback_data="pay_star")],
        [InlineKeyboardButton(text=f"Картой (ЮKassa) · {rub_amount} ₽", callback_data="pay_cash")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def create_settings_keyboard():
    kb_list = [
        [KeyboardButton(text="📱 Установка на телефон"), KeyboardButton(text="💻 Установка на ПК")],
        [KeyboardButton(text="🆘 Поддержка")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)
    return keyboard



def create_profile_keyboard():
    kb_list = [
        [KeyboardButton(text="📂 Мои конфиги")],
        [KeyboardButton(text="✨ Активировать дни")],
        [KeyboardButton(text="🔙 Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=False)



def create_activate_balance_inline(balance_days: int):
    text = f"Активировать: {balance_days} дн." if balance_days > 0 else "Обновить"
    kb_list = [
        [InlineKeyboardButton(text=text, callback_data="activate_balance")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def create_settings_inline(prefs: dict, fav_server: str | None):
    kb_list = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def create_pref_server_inline(current: str | None):
    kb_list = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)

