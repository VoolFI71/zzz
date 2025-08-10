from aiogram import Router, types, F
from keyboards import keyboard

router = Router()

@router.message(F.text == "Выбрать тариф")
async def choose_tariff(message: types.Message):
    # Сначала предлагаем выбрать сервер
    text = (
        "Вы оформляете доступ к услугам GLS VPN.\n\n"
        "- 🔐 Полная конфиденциальность и анонимность\n"
        "- ♾️ Безлимитный трафик\n"
        "- 🚀 Стабильная скорость и мгновенное подключение\n\n"
        "🌍 Доступные локации:\n"
        "├ 🇳🇱 Нидерланды — в разработке\n"
        "├ 🇩🇪 Германия — в разработке\n"
        "├ 🇺🇸 США — в разработке\n"
        "└ 🇫🇮 Финляндия — доступно"
    )
    await message.answer(text, reply_markup=keyboard.create_server_keyboard())
