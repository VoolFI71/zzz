from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard
from database import db
import os
from aiogram.types import FSInputFile
from routes.admin import is_admin
import logging
logger = logging.getLogger(__name__)

AUTH_CODE = os.getenv("AUTH_CODE")  # not used here; kept only if referenced implicitly elsewhere

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
                # Начисляем +2 дня на баланс владельцу кода
                try:
                    await db.add_balance_days(str(owner_tg_id), 2)
                    await message.bot.send_message(
                        int(owner_tg_id),
                        "По вашей реферальной ссылке зарегистрировался новый пользователь. На ваш баланс начислено 2 дня. Активируйте дни в Личном кабинете. \n За каждого пользователя, который купит подписку, вы получаете бонусные дни на баланс"
                    )
                    # Уведомление администратору о реферальной активации
                    try:
                        admin_id = 746560409
                        # username владельца
                        owner_username = "—"
                        try:
                            chat = await message.bot.get_chat(int(owner_tg_id))
                            if getattr(chat, "username", None):
                                owner_username = f"@{chat.username}"
                        except Exception:
                            pass
                        new_username = (f"@{message.from_user.username}" if getattr(message.from_user, "username", None) else "—")
                        await message.bot.send_message(
                            admin_id,
                            f"Реферал активирован: owner_id={owner_tg_id}, owner={owner_username}, new_user_id={user_id}, new_user={new_username}, бонус=2 дн."
                        )
                    except Exception:
                        pass
                    # Сообщение новому пользователю после приветствия
                    referral_bonus_message = (
                        "Вы перешли по реферальной ссылке — её владелец получил 2 дня бесплатной подписки."
                    )
                except Exception:
                    logger.exception("Failed to process referral bonus for owner_tg_id=%s", owner_tg_id)
        else:
            # Пользователь уже активировал реферальную ссылку ранее
            await message.answer("Вы уже использовали реферальную ссылку ранее. Это можно сделать только один раз.")

    start_caption = (
        "👋 Привет! Я — GLS VPN бот.\n"
        "Помогу подключиться к быстрому и безопасному интернету без границ.\n\n"
        "🔐 Безопасное и быстрое подключение\n"
        "🚀 Высокая скорость и стабильность\n"
        "🧩 iOS / Android / Windows / macOS\n\n"
        "🎁 Новый пользователь может один раз активировать пробную подписку на 2 дня.\n\n"
        "✨ Всё просто: выбери тариф, оплати в Telegram и подключайся!\n"
        "\nℹ️ Обход региональных блокировок может не работать у некоторых операторов (Билайн, Мегафон) и может перестать работать в любой момент. Вы всё равно можете использовать VPN."
        "\nЕсли возникнут вопросы — напишите в поддержку."

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
        # Выбираем клавиатуру в зависимости от роли пользователя
        user_keyboard = keyboard.create_admin_keyboard() if is_admin(message.from_user.id) else keyboard.create_keyboard()
        
        if image_path_found:
            await message.answer_photo(photo=FSInputFile(image_path_found), caption=start_caption, reply_markup=user_keyboard)
        else:
            await message.answer("Добро пожаловать! Выберите действие:", reply_markup=user_keyboard)
    except Exception:
        # Фолбэк на случай ошибки при отправке изображения
        user_keyboard = keyboard.create_admin_keyboard() if is_admin(message.from_user.id) else keyboard.create_keyboard()
        await message.answer("Добро пожаловать! Выберите действие:", reply_markup=user_keyboard)

    # Отправляем уведомление о реферальном бонусе после приветствия
    if referral_bonus_message:
        await message.answer(referral_bonus_message)


