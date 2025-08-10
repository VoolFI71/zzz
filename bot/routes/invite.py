from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard
from database import db

router = Router()

@router.message(F.text == "Пригласить")
async def invite_handler(message: types.Message):
    tg_id = str(message.from_user.id)
    referral_code = await db.get_referral_code(tg_id)
    if referral_code:
        # 1. Ссылка
        await message.answer(
            f"Ваша реферальная ссылка:\nhttps://t.me/glsvpn_bot?start={referral_code}")

        # 2. Счётчик приглашённых
        invited = await db.get_referral_count(tg_id) or 0
        await message.answer(
            f"👥 Вы пригласили пользователей: {invited}/7",
            reply_markup=keyboard.create_keyboard(),
        )
    else:
        await message.answer("Не удалось получить реферальный код.", reply_markup=keyboard.create_keyboard())
