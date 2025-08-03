from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard
import aiosqlite
from database import db
import random

router = Router()
async def get_referral_code(tg_id):
    async with aiosqlite.connect("users.db") as conn:
        cursor = await conn.execute("SELECT referral_code FROM users WHERE tg_id = ?", (tg_id,))
        result = await cursor.fetchone()
        if result and result[0]:
            return result[0]
        # Проверяем, есть ли пользователь
        cursor = await conn.execute("SELECT tg_id FROM users WHERE tg_id = ?", (tg_id,))
        user_exists = await cursor.fetchone()
        if not user_exists:
            await conn.execute("INSERT INTO users (tg_id) VALUES (?)", (tg_id,))
            await conn.commit()
        referral_code = str(random.randint(10_000_000_000, 20_000_000_000))
        await conn.execute("UPDATE users SET referral_code = ? WHERE tg_id = ?", (referral_code, tg_id))
        await conn.commit()
        return referral_code

# Функция get_referral_code(tg_id) работает так:
# 1. Проверяет, есть ли у пользователя с этим tg_id уже реферальный код.
#    Если есть — возвращает его.
# 2. Если кода нет, проверяет, существует ли пользователь в таблице users.
#    Если пользователя нет — добавляет его (INSERT INTO users).
# 3. Генерирует новый реферальный код (случайное число).
# 4. Сохраняет этот код для пользователя (UPDATE users SET referral_code).
# 5. Возвращает новый реферальный код.

# Таким образом, для каждого пользователя реферальный код создаётся только один раз и сохраняется в базе.
# При повторном запросе возвращается уже сохранённый код.

@router.message(F.text == "Пригласить")
async def invite_handler(message: types.Message):
    tg_id = str(message.from_user.id)
    referral_code = await db.get_referral_code(tg_id)
    if referral_code:
        await message.answer(f"Ваша реферальная ссылка: https://t.me/godnet_vpnbot?start={referral_code}", reply_markup=keyboard.create_keyboard())
    else:
        await message.answer("Не удалось получить реферальный код.", reply_markup=keyboard.create_keyboard())
