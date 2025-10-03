from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import aiohttp
import time
import os

logger = logging.getLogger(__name__)

router = Router()

# API настройки
API_BASE_URL = "http://fastapi:8080"
AUTH_CODE = os.getenv("AUTH_CODE")

class AdminStates(StatesGroup):
    waiting_for_user_search = State()

# Импортируем is_admin из main модуля
from .main import is_admin

@router.callback_query(F.data == "admin_search_user")
async def start_user_search(callback: types.CallbackQuery, state: FSMContext):
    """Начинает поиск пользователя по Telegram ID."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        
        await callback.message.edit_text(
            "🔍 Поиск пользователя\n\n"
            "Введите Telegram ID пользователя для поиска:"
        )
        await state.set_state(AdminStates.waiting_for_user_search)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in start_user_search: {e}")
        await callback.answer("❌ Ошибка при запуске поиска", show_alert=True)

@router.message(AdminStates.waiting_for_user_search)
async def process_user_search(message: types.Message, state: FSMContext):
    """Обрабатывает поиск пользователя."""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа.")
        await state.clear()
        return
    
    try:
        user_id = int(message.text.strip())
        user_info = await get_user_info(user_id)
        
        if user_info:
            info_text = (
                f"👤 Информация о пользователе\n\n"
                f"🆔 Telegram ID: {user_info['tg_id']}\n"
                f"🎁 Использовал пробную подписку: {'Да' if user_info['trial_used'] else 'Нет'}\n"
                f"💰 Баланс дней: {user_info['balance']}\n"
                f"🤝 Количество рефералов: {user_info['referral_count']}\n"
                f"🔗 Реферальный код: {user_info['referral_code']}\n"
                f"📅 Дата регистрации: {user_info['created_at']}\n"
                f"⚙️ Активных конфигов: {user_info['active_configs']}"
            )
            await message.answer(info_text)
        else:
            await message.answer("❌ Пользователь не найден в базе данных.")
            
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите числовой ID.")
        return
    except Exception as e:
        logger.error(f"Error searching user: {e}")
        await message.answer(f"❌ Ошибка при поиске: {str(e)}")
    
    await state.clear()

async def get_user_info(tg_id: int) -> dict | None:
    """Получает информацию о пользователе из bot БД."""
    try:
        import aiosqlite
        
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT tg_id, trial_3d_used, balance, referral_count, referral_code, created_at FROM users WHERE tg_id = ?",
                    (str(tg_id),)
                )
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                # Получаем количество активных конфигов через API
                active_configs = 0
                try:
                    async with aiohttp.ClientSession() as session:
                        url = f"{API_BASE_URL}/usercodes/{tg_id}"
                        headers = {"X-API-Key": AUTH_CODE}
                        async with session.get(url, headers=headers, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                current_time = int(time.time())
                                active_configs = len([
                                    item for item in data 
                                    if item.get("time_end", 0) > current_time
                                ])
                except Exception as e:
                    logger.warning(f"Error getting active configs for user {tg_id}: {e}")
                
                return {
                    'tg_id': row[0],
                    'trial_used': bool(row[1]),
                    'balance': row[2] or 0,
                    'referral_count': row[3] or 0,
                    'referral_code': row[4] or "Не установлен",
                    'created_at': row[5] or "Неизвестно",
                    'active_configs': active_configs
                }
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return None
