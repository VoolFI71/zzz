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
    bonus_message_needed = False
    configs_available = True
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
                bonus_message_needed = True  # для сообщения пользователю
                # Проверяем наличие свободных конфигов (любого сервера) перед выдачей бонуса
                configs_available = False
                preferred_servers = ["fi", "nl"]
                selected_server = None
                for server_code in preferred_servers:
                    if await check_available_configs(server_code):
                        configs_available = True
                        selected_server = server_code
                        break

            try:
                if configs_available:
                    # Отправляем уведомление владельцу реферального кода
                    await message.bot.send_message(
                        int(owner_tg_id),
                        "По вашей реферальной ссылке зарегистрировался новый пользователь. Вы получаете доступ к нашему VPN на 3 дня бесплатно."
                    )

                    data = {
                        "id": str(owner_tg_id),
                        "time": 3,
                        "server": selected_server,
                    }

                    from utils import get_session
                    session = await get_session()
                    try:
                        async with session.post(urlupdate, json=data, headers={"X-API-Key": AUTH_CODE}) as response:
                            if response.status == 200:
                                await message.bot.send_message(int(owner_tg_id), "Конфиг для подключения можно найти в личном кабинете.")
                    except Exception:
                        pass  # сетевой сбой – молча игнорируем
                else:
                    # Свободных конфигов нет, но реферальная ссылка засчитана
                    await message.bot.send_message(
                        int(owner_tg_id),
                        "По вашей реферальной ссылке зарегистрировался новый пользователь! К сожалению, в данный момент нет свободных конфигураций. При желании напишите в поддержку"
                    )
            except Exception:
                pass  # Любая неожиданная ошибка – не прерываем flow
        else:
            # Пользователь уже активировал реферальную ссылку ранее
            await message.answer("Вы уже использовали реферальную ссылку ранее. Это можно сделать только один раз.")

    start_caption = (
        "⚡ Привет! Я — твой личный помощник GLS VPN.\n"
        "Помогу получить быстрый и безопасный интернет без границ.\n\n"
        "🔓 Обход блокировок и DPI\n"
        "🚀 Высокая скорость и стабильность\n"
        "📱 iOS / Android / Windows / macOS\n\n"
        "Всё просто: выбери тариф, оплати в Telegram и подключайся!"
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


