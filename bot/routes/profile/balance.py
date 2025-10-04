"""
Управление балансом пользователя.
"""

from aiogram import Router, F, types
from keyboards import keyboard
from utils import check_all_servers_available
from database import db

router = Router()

@router.message(F.text.in_({"Активировать дни", "✨ Активировать дни"}))
async def show_balance_activation(message: types.Message):
    """Показывает баланс дней и предлагает активацию."""
    tg_id = str(message.from_user.id)
    try:
        days = await db.get_balance_days(tg_id)
    except Exception:
        days = 0
    if days <= 0:
        await message.answer("На вашем балансе нет дней для активации.", reply_markup=keyboard.create_profile_keyboard())
        return

    # Проверяем доступность серверов перед показом кнопки активации
    if not await check_all_servers_available():
        await message.answer(
            f"На балансе: {days} дн.\n\n"
            "❌ К сожалению, сейчас не все серверы доступны для активации бонусных дней.\n"
            "Для активации дней должны быть доступны все серверы.\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=keyboard.create_profile_keyboard()
        )
        return

    await message.answer(
        f"На балансе: {days} дн. Нажмите кнопку ниже, чтобы активировать их как подписку.",
        reply_markup=keyboard.create_activate_balance_inline(days)
    )
