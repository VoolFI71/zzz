from aiogram import Router, types, F
from keyboards import keyboard

router = Router()

# Поддерживаем старый и новый варианты текста кнопки
@router.message(F.text.in_({"Выбрать тариф", "📦 Выбрать тариф"}))
async def choose_tariff(message: types.Message):
    # Сначала предлагаем выбрать сервер
    text = (
        "<b>Оформление GLS VPN</b>\n\n"
        "• 🔐 Конфиденциальность и анонимность\n"
        "• ♾️ Безлимитный трафик\n"
        "• 🚀 Стабильная скорость\n\n"
        "<b>Доступные локации</b>\n"
        "├ 🇳🇱 Нидерланды — в разработке\n"
        "├ 🇩🇪 Германия — в разработке\n"
        "├ 🇺🇸 США — в разработке\n"
        "└ 🇫🇮 Финляндия — доступно\n\n"
        "Мы маскируем трафик под VK — это делает мобильный интернет безлимитным, \nесли у оператора есть опция безлимитных соцсетей (VK)."
    )
    await message.answer(text, reply_markup=keyboard.create_server_keyboard(), parse_mode="HTML", disable_web_page_preview=True)
