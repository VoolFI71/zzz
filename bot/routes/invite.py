from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard
import aiosqlite
from database import db
import random

router = Router()

@router.message(F.text == "Пригласить")
async def invite_handler(message: types.Message):
    tg_id = str(message.from_user.id)
    referral_code = await db.get_referral_code(tg_id)
    if referral_code:
        await message.answer(f"Ваша реферальная ссылка: https://t.me/godnet_vpnbot?start={referral_code}", reply_markup=keyboard.create_keyboard())
    else:
        await message.answer("Не удалось получить реферальный код.", reply_markup=keyboard.create_keyboard())
