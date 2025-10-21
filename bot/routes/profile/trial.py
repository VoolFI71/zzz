"""
Функции пробной подписки.
"""

import os
import aiohttp
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from utils import should_throttle, acquire_action_lock, check_all_servers_available, get_session
from keyboards.ui_labels import BTN_TRIAL
from database import db
from keyboards import keyboard

router = Router()

@router.message(F.text.in_({
    "Пробная 3 дня",
    "🎁 Пробная 3 дня",
    "Пробные 3 дня",
    "🎁 Пробные 3 дня",
    "Пробный доступ 3 дня",
    "🎁 Пробный доступ 3 дня",
    BTN_TRIAL,
}))
async def free_trial(message: types.Message):
    """Активация пробной подписки на 3 дня."""
    user_id = message.from_user.id
    # Throttle repeated clicks
    throttled, retry_after = should_throttle(user_id, "free_trial", cooldown_seconds=5.0)
    if throttled:
        await message.answer(f"Слишком часто. Попробуйте через {int(retry_after)+1} сек.")
        return
    try:
        await db.ensure_user_row(str(user_id))
        if await db.has_used_trial_3d(str(user_id)):
            await message.answer("Вы уже активировали пробную подписку ранее.")
            return
    except Exception:
        await message.answer("Ошибка. Попробуйте позже.")
        return

    # Проверяем доступность серверов перед выдачей пробной подписки
    if not await check_all_servers_available():
        await message.answer(
            "❌ К сожалению, сейчас не все серверы доступны для пробной подписки.\n"
            "Для активации пробной подписки должны быть доступны все серверы.\n"
            "Попробуйте позже или обратитесь в поддержку."
        )
        return

    # Показываем индикатор прогресса
    progress_msg = await message.answer("🔄 Активирую пробную подписку...")
    
    # Выдаем конфиги на всех серверах из SERVER_ORDER (как при покупке подписки)
    server_order_env = os.getenv("SERVER_ORDER", "ge")
    servers_to_use = [s.strip().lower() for s in server_order_env.split(',') if s.strip()]
    # Выбираем по одному варианту на регион (ge*)
    try:
        from utils import pick_servers_one_per_region
        servers_to_use = await pick_servers_one_per_region(servers_to_use)
    except Exception:
        pass

    # Выдаём бесплатные 3 дня на всех серверах
    AUTH_CODE = os.getenv("AUTH_CODE")
    urlupdate = "http://fastapi:8080/giveconfig"
    success_count = 0
    failed_servers = []
    
    try:
        session = await get_session()
        async with acquire_action_lock(user_id, "free_trial"):
            for server in servers_to_use:
                data = {"time": 3, "id": str(user_id), "server": server}
                async with session.post(urlupdate, json=data, headers={"X-API-Key": AUTH_CODE}) as resp:
                    if resp.status == 200:
                        success_count += 1
                    else:
                        failed_servers.append(server)
            
            if success_count > 0:
                # Обновляем прогресс
                await progress_msg.edit_text("✅ Пробная подписка активирована! Настраиваю доступ...")
                
                await db.set_trial_3d_used(str(user_id))
                base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
                try:
                    sub_url = f"http://fastapi:8080/sub/{user_id}"
                    async with session.get(sub_url, headers={"X-API-Key": AUTH_CODE}) as sub_resp:
                        if sub_resp.status == 200:
                            sub_data = await sub_resp.json()
                            sub_key = sub_data.get("sub_key")
                            if sub_key:
                                web_url = f"{base}/subscription/{sub_key}"
                            else:
                                web_url = f"{base}/subscription"
                        else:
                            web_url = f"{base}/subscription"
                except Exception:
                    # Fallback на старую ссылку, если что-то пошло не так
                    web_url = f"{base}/subscription"
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📲 Добавить подписку в V2rayTun", web_app=WebAppInfo(url=web_url))],
                    [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_sub")],
                ])
                await message.answer(f"🎉 Пробная подписка на 3 дня активирована на {success_count} серверах!", reply_markup=kb)
                await message.answer("💡 Подписка может быть не добавлена при нажатии на кнопку на сайте, в этом случае необходимо скопировать ссылку на подписку и вставить в V2rayTun вручную.")

                try:
                    admin_id = 746560409
                    at_username = (f"@{message.from_user.username}" if getattr(message.from_user, "username", None) else "—")
                    await message.bot.send_message(admin_id, f"Активирована пробная подписка: user_id={user_id}, user={at_username}, серверов={success_count}, срок=3 дн.")
                except Exception:
                    pass
            else:
                await message.answer("❌ Не удалось активировать пробную подписку. Серверы временно недоступны. Попробуйте через 5-10 минут.", reply_markup=keyboard.create_keyboard())
                
            if failed_servers:
                await message.answer(f"⚠️ Частично активировано: не удалось создать конфиги на серверах {', '.join(failed_servers)}. Остальные серверы работают.", reply_markup=keyboard.create_keyboard())
                
    except aiohttp.ClientError:
        await message.answer("🌐 Проблемы с подключением к серверам. Проверьте интернет и попробуйте позже.", reply_markup=keyboard.create_keyboard())
