"""
Unified UI labels for buttons and common messages to keep a single style
across the bot. Import and reuse in keyboards and route handlers.
"""

# Main menu
BTN_TARIFF = "📦 Выбрать тариф"
BTN_PROFILE = "👤 Личный кабинет"
BTN_TRIAL = "🎁 Пробные 3 дня"
BTN_INVITE = "🤝 Пригласить"
BTN_GUIDE = "🛠️ Инструкция"
BTN_SUPPORT = "🆘 Поддержка"
BTN_BACK = "🔙 Назад"

# Profile
BTN_MY_CONFIGS = "📂 Мои конфиги"
BTN_ACTIVATE_DAYS = "✨ Активировать дни"

# Settings / Guides
BTN_SETUP_PHONE = "📱 Установка на телефон"
BTN_SETUP_PC = "💻 Установка на ПК"

# Inline actions
BTN_ADD_SUB_WEBAPP = "📲 Добавить подписку в V2rayTun"
BTN_COPY_SUB = "📋 Скопировать ссылку"
BTN_REFRESH = "🔁 Обновить"
BTN_CLOSE = "✖️ Закрыть"

# Tariffs (inline)
def tariff_1m_label(stars: int, rub: int) -> str:
    return f"1 месяц · {stars} ⭐ / {rub} ₽"


def tariff_3m_label(stars: int, rub: int) -> str:
    return f"3 месяца · {stars} ⭐ / {rub} ₽"


# Common user-facing messages (HTML safe where applicable)
MSG_START_BRIEF = (
    "🛡️ <b>GLS VPN</b>\n\n"
    "• 🔐 Защита и приватность\n"
    "• ⚡ Стабильная скорость\n"
    "• 📱 2 минуты на настройку\n\n"
    "🎁 3 дня бесплатно — чтобы попробовать."
)

MSG_PROFILE_TITLE = "📂 <b>Ваши конфигурации</b>"
MSG_PROFILE_NO_CONFIGS = (
    "📂 У вас пока нет активных конфигураций.\n\n"
    "🎁 Получите 3 дня бесплатно или выберите тариф."
)
MSG_PROFILE_IMPORT_NOTE = (
    "Если импорт не сработает через мини‑приложение, скопируйте ссылку и вставьте в V2rayTun вручную."
)

MSG_COPY_SUB_PROMPT = "Скопируйте ссылку"

MSG_ERR_NOT_FOUND = (
    "Конфигурации не найдены. Оформите подписку или активируйте дни в Личном кабинете."
)
MSG_ERR_TIMEOUT = "Сервер недоступен. Попробуйте через 2–3 минуты."
MSG_ERR_NETWORK = "🌐 Проблемы с подключением. Проверьте интернет и попробуйте позже."
MSG_ERR_GENERIC = "❌ Не удалось выполнить действие. Попробуйте позже или обратитесь в поддержку."
MSG_ERR_API = "Ошибка. Попробуйте позже."

MSG_ANTIFLOOD = "Немного подождите (≈1.5 сек) — обрабатываем предыдущую команду."


