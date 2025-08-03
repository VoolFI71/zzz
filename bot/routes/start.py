from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard
from database import db
import os
import aiohttp  # добавлен импорт
from aiogram import Bot  # если нужен тип Bot

AUTH_CODE = os.getenv("AUTH_CODE")
urlupdate = "http://fastapi:8080/giveconfig"  # добавлено определение urlupdate
router = Router()

@router.message(Command('start'))
async def start_command(message: types.Message):
    args = message.text.split()
    user_id = message.from_user.id
    if len(args) > 1:
        referral_code = args[1]

        owner_tg_id = await db.get_tg_id_by_referral_code(referral_code)
        if owner_tg_id is None:
            print("Неверная реферальная ссылка")

        # Проверяем, что пользователь не использует свой код
        if not owner_tg_id or owner_tg_id == str(user_id):
            return await message.answer("Вы не можете активировать свою собственную реферальную ссылку!")

        is_new_user = await db.is_first_time_user(user_id)

        if is_new_user:
            # Добавляем связь между пользователями (реферралом и владельцем ссылки)
            await db.add_referral_by(user_id, referral_code)

            try:
                # Отправляем уведомление владельцу реферального кода
                await message.bot.send_message(
                    int(owner_tg_id),
                    f"По вашей реферальной ссылке зарегистрировался новый пользователь. Вы получаете доступ к нашему VPN на 3 дня бесплатно."
                )
                data = {
                    "auth": str(AUTH_CODE),
                    "id": str(owner_tg_id),
                    "time": 3
                }
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(urlupdate, json=data) as response:
                            if response.status == 200:
                                # Отправляем уведомление владельцу реферального кода
                                await message.bot.send_message(int(owner_tg_id), "Конфиг для подключения можно найти в личном кабинете.")
                    except Exception:
                        pass  # Игнорируем ошибку, если пользователь не может получить сообщение
            except Exception:
                pass  # Игнорируем ошибку, если пользователь не может получить сообщение
        else:
            # Пользователь уже активировал реферальную ссылку ранее
            await message.answer("Вы уже использовали реферальную ссылку ранее. Это можно сделать только один раз.")
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=keyboard.create_keyboard())


@router.message(F.text == "Выбрать тариф")
async def choose_tariff(message: types.Message):
    await message.answer("Выберите тариф:", reply_markup=keyboard.create_tariff_keyboard())
