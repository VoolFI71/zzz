"""
Основные функции профиля пользователя.
"""

import os
from aiogram import Router, F, types
from keyboards import keyboard

router = Router()

# Читает первое непустое значение из списка env-ключей
def _env_any(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default

# Поддерживаем старый и новый варианты кнопки
@router.message(F.text.in_({"Личный кабинет", "👤 Личный кабинет"}))
async def my_account(message: types.Message):
    """Показывает главное меню личного кабинета."""
    # Переходим в подменю профиля
    await message.answer("Личный кабинет:", reply_markup=keyboard.create_profile_keyboard())
