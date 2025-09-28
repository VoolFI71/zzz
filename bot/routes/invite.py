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
                f"🎉 Вы пригласили {invited} из {limit}. Лимит достигнут!\n\n"
                "Бонус +2 дня начисляется только за первых 7 приглашённых.\n"
                "За приглашения сверх 7 — дополнительные +2 дня не начисляются, но начисляется процент с каждого кто оплатит подписку.\n\n"
                "🧪 Новый пользователь может активировать пробную подписку на 3 дня.\n"
                "Спасибо, что делитесь GLS VPN!"
            )
        else:
            remaining = limit - invited
            text = (
                "🎁 За каждого приглашённого — +2 дня на баланс (за первых 7).\n"
                f"👥 Прогресс: {invited}/{limit}\n"
                f"📣 Осталось пригласить: {remaining}.\n\n"
                "🎯 Бонус за цель: при достижении 7/7 — дополнительно +15 дней.\n\n"
                "🧪 Новый пользователь может активировать пробную подписку на 3 дня.\n\n"
                "Поделитесь ссылкой выше — как только друг перейдёт по реферальной ссылке, бонус +2 дня упадёт на баланс.\n"
                "Если приглашённый оплатит подписку, вы получите 10% бонусными днями."
            )
        await message.answer(text, reply_markup=keyboard.create_keyboard())
    else:
        await message.answer("Не удалось получить реферальный код.", reply_markup=keyboard.create_keyboard())
