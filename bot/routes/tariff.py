from aiogram import Router, types, F
from keyboards import keyboard
from keyboards.ui_labels import BTN_TARIFF

router = Router()

# Поддерживаем старые варианты текста, основной — константа
@router.message(F.text.in_({"Выбрать тариф", "📦 Выбрать тариф", BTN_TARIFF}))
async def choose_tariff(message: types.Message):
    # Сначала предлагаем выбрать сервер
    text = (
        "<b>Подписка на GLS VPN</b>\n\n"
        "🔐 Приватность • ♾️ Безлимит • 🚀 Стабильная скорость\n"
        "🌍 Доступ к нужным сайтам и приложениям\n\n"
        "<b>Доступные локации</b>\n"
        "├ 🇳🇱 Нидерланды — в разработке\n"
        "├ 🇺🇸 США — в разработке\n"
        "└🇩🇪 Германия — доступно\n\n"
        "<b>Как оформить</b>\n"
        "1) Выберите срок подписки ниже\n"
        "2) Оплатите звёздами или картой\n"
        "3) Добавьте подписку в V2rayTun\n\n"
        "Если появятся вопросы — откройте Поддержку."
    )
    await message.answer(text, reply_markup=keyboard.create_tariff_keyboard(), parse_mode="HTML", disable_web_page_preview=True)
