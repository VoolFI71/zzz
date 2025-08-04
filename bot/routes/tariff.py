from aiogram import Router, types, F
from keyboards import keyboard

router = Router()

@router.message(F.text == "Выбрать тариф")
async def choose_tariff(message: types.Message):
    await message.answer("Выберите тариф:", reply_markup=keyboard.create_tariff_keyboard())
