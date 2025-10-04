"""
Callback обработчики для профиля.
"""

import os
import aiohttp
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import acquire_action_lock, get_session
from database import db

router = Router()

AUTH_CODE = os.getenv("AUTH_CODE")

@router.callback_query(F.data.startswith("copy_config_"))
async def copy_config_callback(callback: types.CallbackQuery):
    """Теперь отдаём ссылку на подписку, которая подтянет все конфиги автоматически."""
    try:
        # idx из callback нам больше не нужен, но парсим безопасно для обратной совместимости
        _ = int(callback.data.split("_")[-1]) if callback.data.rsplit("_", 1)[-1].isdigit() else None
    except Exception:
        pass

    user_id = callback.from_user.id
    headers = {"X-API-Key": AUTH_CODE}

    try:
        session = await get_session()
        async with acquire_action_lock(user_id, "copy_config"):
            # Получаем постоянный sub_key из внутреннего API
            sub_url_api = f"http://fastapi:8080/sub/{user_id}"
            async with session.get(sub_url_api, timeout=10, headers=headers) as resp:
                if resp.status != 200:
                    await callback.answer("Ошибка. Попробуйте позже", show_alert=True)
                    return
                data = await resp.json()
                sub_key = data.get("sub_key")
                if not sub_key:
                    await callback.answer("Не удалось получить ссылку", show_alert=True)
                    return
            # Формируем публичную ссылку подписки
            base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
            web_url = f"{base}/subscription/{sub_key}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📲 Добавить подписку в V2rayTun", url=web_url)],
                [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_sub")],
            ])
            await callback.message.answer("Ваша подписка:", reply_markup=kb, disable_web_page_preview=True)
            await callback.answer()
    except aiohttp.ClientError:
        await callback.answer("Ошибка сети", show_alert=True)
    except Exception:
        await callback.answer("Ошибка", show_alert=True)

@router.callback_query(F.data == "copy_sub")
async def copy_subscription_callback(callback: types.CallbackQuery):
    """Отправляет пользователю его ссылку на подписку для копирования."""
    user_id = callback.from_user.id
    headers = {"X-API-Key": AUTH_CODE}
    try:
        session = await get_session()
        sub_url_api = f"http://fastapi:8080/sub/{user_id}"
        async with acquire_action_lock(user_id, "copy_sub"):
            async with session.get(sub_url_api, timeout=10, headers=headers) as resp:
                if resp.status != 200:
                    await callback.answer("Ошибка", show_alert=True)
                    return
                data = await resp.json()
                sub_key = data.get("sub_key")
                if not sub_key:
                    # Пытаемся создать sub_key принудительно
                    try:
                        sub_key = await db.get_or_create_sub_key(str(user_id))
                    except Exception:
                        await callback.answer("Нет ссылки", show_alert=True)
                        return
        base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
        web_url = f"{base}/subscription/{sub_key}"
        # Редактируем текущее сообщение: показываем только ссылку без кнопок
        try:
            await callback.message.edit_text(web_url, disable_web_page_preview=True)
        except Exception:
            try:
                # Если редактирование недоступно (старое сообщение) — отправим новым сообщением
                await callback.message.answer(web_url, disable_web_page_preview=True)
            except Exception:
                pass
        # Сообщаем пользователю
        try:
            await callback.answer("Скопируйте ссылку", show_alert=False)
        except Exception:
            pass
    except Exception:
        try:
            await callback.answer("Ошибка", show_alert=True)
        except Exception:
            pass

@router.callback_query(F.data == "delmsg")
async def delete_message_callback(callback: types.CallbackQuery):
    """Удаляет сообщение."""
    try:
        await callback.message.delete()
    except Exception:
        pass
    try:
        await callback.answer()
    except Exception:
        pass
