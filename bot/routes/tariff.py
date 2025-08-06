from aiogram import Router, types, F
from keyboards import keyboard

router = Router()

@router.message(F.text == "Выбрать тариф")
async def choose_tariff(message: types.Message):
    # Сначала предлагаем выбрать сервер
    await message.answer("Выберите сервер:", reply_markup=keyboard.create_server_keyboard())
