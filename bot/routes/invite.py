from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard
from database import db

router = Router()

@router.message(F.text.in_({"Пригласить", "🤝 Пригласить"}))
async def invite_handler(message: types.Message):
    tg_id = str(message.from_user.id)
    referral_code = await db.get_referral_code(tg_id)
    if referral_code:
        # 1. Ссылка
        await message.answer(
            f"Ваша реферальная ссылка:\nhttps://t.me/glsvpn_bot?start={referral_code}")

        # 2. Счётчик приглашённых (улучшённый текст)
        invited = await db.get_referral_count(tg_id) or 0
        limit = 7
        if invited >= limit:
            text = (
                f"🎉 Вы пригласили {invited} из {limit}. Лимит достигнут!\n"
                "🧪 Новый пользователь может активировать пробную подписку на 3 дня.\n"
                "Спасибо, что делитесь GLS VPN!"
            )
        else:
            remaining = limit - invited
            text = (
                "🎁 За каждого приглашённого — 3 дня на ваш баланс (активируйте в Личном кабинете).\n"
                f"👥 Ваш прогресс: {invited}/{limit}\n"
                f"📣 Осталось пригласить: {remaining}.\n"
                "🧪 Новый пользователь может активировать пробную подписку на 3 дня.\n"
                "Поделитесь ссылкой выше — как только друг перейдёт по реферальной ссылке, бонус 3 дня упадёт на баланс."
            )
        await message.answer(text, reply_markup=keyboard.create_keyboard())
    else:
        await message.answer("Не удалось получить реферальный код.", reply_markup=keyboard.create_keyboard())
