from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard
from keyboards.ui_labels import MSG_START_BRIEF, BTN_TRIAL, BTN_TARIFF, BTN_GUIDE, BTN_SUPPORT
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
            result = await db.add_referral_by(user_id, referral_code)
            if result.get("award_2d"):
                # Начисляем +2 дня на баланс владельцу кода (только до 7 пригл.)
                try:
                    await db.add_balance_days(str(owner_tg_id), 2)
                    await message.bot.send_message(
                        int(owner_tg_id),
                        "Новый пользователь перешёл по вашей реферальной ссылке. На баланс начислено +2 дня. Активируйте дни в Личном кабинете — они продлят все ваши конфиги."
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
                            f"Реферал активирован: owner_id={owner_tg_id}, owner={owner_username}, new_user_id={user_id}, new_user={new_username}, бонус=+2 дн., счётчик={result.get('new_count')}"
                        )
                    except Exception:
                        pass
                    # Сообщение новому пользователю после приветствия
                    referral_bonus_message = (
                        "Вы перешли по реферальной ссылке — её владелец получил +2 дня."
                    )
                except Exception:
                    logger.exception("Failed to process referral bonus for owner_tg_id=%s", owner_tg_id)

            # Дополнительный бонус при достижении 7/7 — единовременно +15 дней
            if result.get("award_15d"):
                try:
                    await db.add_balance_days(str(owner_tg_id), 15)
                    await message.bot.send_message(
                        int(owner_tg_id),
                        "Поздравляем! Вы пригласили 7 друзей. На ваш баланс начислено дополнительно +15 дней. Активируйте дни в Личном кабинете — они продлят все ваши конфиги."
                    )
                except Exception:
                    logger.exception("Failed to grant +15d milestone bonus to %s", owner_tg_id)
        else:
            # Пользователь уже активировал реферальную ссылку ранее
            await message.answer("Вы уже использовали реферальную ссылку ранее. Это можно сделать только один раз.")

    start_caption = (
        f"{MSG_START_BRIEF}\n\n"
        "💡 <b>Как начать</b>\n"
        f"— Нажмите «{BTN_TRIAL}» или «{BTN_TARIFF}»\n"
        f"— При необходимости — «{BTN_GUIDE}»\n\n"
        f"🆘 <b>Нужна помощь?</b> Откройте «{BTN_SUPPORT}»"
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
            await message.answer_photo(photo=FSInputFile(image_path_found), caption=start_caption, reply_markup=user_keyboard, parse_mode="HTML")
        else:
            await message.answer(start_caption, reply_markup=user_keyboard, parse_mode="HTML")
    except Exception:
        # Фолбэк на случай ошибки при отправке изображения
        user_keyboard = keyboard.create_admin_keyboard() if is_admin(message.from_user.id) else keyboard.create_keyboard()
        await message.answer(start_caption, reply_markup=user_keyboard, parse_mode="HTML")

    # Отправляем уведомление о реферальном бонусе после приветствия
    if referral_bonus_message:
        await message.answer(referral_bonus_message)


