from aiogram import Router, types, F
from keyboards import keyboard

router = Router()

# Поддерживаем старый и новый варианты текста кнопки
@router.message(F.text.in_({"Выбрать тариф", "📦 Выбрать тариф"}))
async def choose_tariff(message: types.Message):
    # Временно отключена возможность покупки
    text = (
        "🚧 <b>Покупка временно недоступна</b>\n\n"
        "В данный момент мы проводим технические работы.\n"
        "Попробуйте позже."
    )
    await message.answer(text, parse_mode="HTML")
