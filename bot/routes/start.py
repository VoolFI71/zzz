from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard
from database import db
import os
import aiohttp  # добавлен импорт
from aiogram import Bot  # если нужен тип Bot
from aiogram.types import FSInputFile
from utils import check_available_configs
import logging
logger = logging.getLogger(__name__)

AUTH_CODE = os.getenv("AUTH_CODE")
urlupdate = "http://fastapi:8080/giveconfig"  # внутренний адрес API

router = Router()

@router.message(Command('start'))
async def start_command(message: types.Message):
    args = message.text.split()
    user_id = message.from_user.id
    referral_bonus_message: str | None = None
    logger.info(f"/start received from {user_id} with args={args}")
    if len(args) > 1:
        referral_code = args[1]

        owner_tg_id = await db.get_tg_id_by_referral_code(referral_code)
        if owner_tg_id is None:
            return await message.answer("Неверная реферальная ссылка!")

        # Проверяем, что пользователь не использует свой код
        if owner_tg_id == str(user_id):
            return await message.answer("Вы не можете активировать свою собственную реферальную ссылку!")

        is_new_user = await db.is_first_time_user(user_id)

        if is_new_user:
            # Добавляем связь между пользователями (реферралом и владельцем ссылки)
            bonus_eligible = await db.add_referral_by(user_id, referral_code)
            if bonus_eligible:
                # Начисляем +3 дня на баланс владельцу кода
                try:
                    await db.add_balance_days(str(owner_tg_id), 3)
                    await message.bot.send_message(
                        int(owner_tg_id),
                        "По вашей реферальной ссылке зарегистрировался новый пользователь. На ваш баланс начислено 3 дня. Активируйте дни в Личном кабинете."
                    )
                    # Сообщение новому пользователю после приветствия
                    referral_bonus_message = (
                        "Вы перешли по реферальной ссылке — её владелец получил 3 дня бесплатной подписки."
                    )
                except Exception:
                    logger.exception("Failed to process referral bonus for owner_tg_id=%s", owner_tg_id)
        else:
            # Пользователь уже активировал реферальную ссылку ранее
            await message.answer("Вы уже использовали реферальную ссылку ранее. Это можно сделать только один раз.")

    start_caption = (
        "⚡ Привет! Я — твой личный помощник GLS VPN.\n"
        "Помогу получить быстрый и безопасный интернет без границ.\n\n"
        "🔓 Обход блокировок и DPI\n"
        "🚀 Высокая скорость и стабильность\n"
        "📱 iOS / Android / Windows / macOS\n\n"
        "🧪 Новый пользователь может один раз активировать пробную подписку на 3 дня.\n\n"
        "Всё просто: выбери тариф, оплати в Telegram и подключайся!"
        "\n\n В данный момент обход региональных блокировок не работает на Билайне, Мегафоне и зависит от региона. Но вы можете продолжить использовать VPN."
        "\n При возникновении вопросов, обращайтесь в поддержку."

    )

    try:
        # Ищем start.jpg локально без переменных окружения
        routes_dir = os.path.dirname(__file__)
        bot_root = os.path.abspath(os.path.join(routes_dir, ".."))
        project_root = os.path.abspath(os.path.join(routes_dir, "..", ".."))
        candidate_paths = [
            os.path.join(project_root, "start.jpg"),
            os.path.join(bot_root, "start.jpg"),
            os.path.join(os.getcwd(), "start.jpg"),
        ]

        image_path_found = next((p for p in candidate_paths if os.path.exists(p)), None)
        if image_path_found:
            await message.answer_photo(photo=FSInputFile(image_path_found), caption=start_caption, reply_markup=keyboard.create_keyboard())
        else:
            await message.answer("Добро пожаловать! Выберите действие:", reply_markup=keyboard.create_keyboard())
    except Exception:
        # Фолбэк на случай ошибки при отправке изображения
        await message.answer("Добро пожаловать! Выберите действие:", reply_markup=keyboard.create_keyboard())

    # Отправляем уведомление о реферальном бонусе после приветствия
    if referral_bonus_message:
        await message.answer(referral_bonus_message)


