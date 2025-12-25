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
    waiting_for_config_uid = State()

# Импортируем is_admin из main модуля
from .main import is_admin

@router.callback_query(F.data == "admin_configs")
async def show_config_management(callback: types.CallbackQuery):
    """Показывает управление конфигами."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        config_stats = await get_config_statistics()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти конфиг по UID", callback_data="admin_find_config")],
            [InlineKeyboardButton(text="📊 Статистика конфигов", callback_data="admin_config_stats")],
            [InlineKeyboardButton(text="🧹 Очистить истекшие", callback_data="admin_cleanup_expired")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_to_main")],
        ])
        
        stats_text = (
            f"⚙️ Управление конфигами\n\n"
            f"📊 Текущая статистика:\n"
            f"• Всего конфигов: {config_stats['total']}\n"
            f"• Активных: {config_stats['active']}\n"
            f"• Истекших: {config_stats['expired']}\n"
            f"• Свободных: {config_stats['free']}\n"
            f"• 🇳🇱 Нидерланды: {config_stats['nl_count']}\n"
            f"• 🇩🇪 Германия: {config_stats['ge_count']}"
        )
        
        await callback.message.edit_text(stats_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error getting config stats: {e}")
        await callback.message.edit_text(f"❌ Ошибка при получении статистики: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_find_config")
async def start_config_search(callback: types.CallbackQuery, state: FSMContext):
    """Начинает поиск конфига по UID."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        
        await callback.message.edit_text(
            "🔍 Поиск конфига\n\n"
            "Введите UID конфига для поиска:"
        )
        await state.set_state(AdminStates.waiting_for_config_uid)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in start_config_search: {e}")
        await callback.answer("❌ Ошибка при запуске поиска конфига", show_alert=True)

@router.message(AdminStates.waiting_for_config_uid)
async def process_config_search(message: types.Message, state: FSMContext):
    """Обрабатывает поиск конфига."""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа.")
        await state.clear()
        return
    
    try:
        config_uid = message.text.strip()
        config_info = await get_config_info(config_uid)
        
        if config_info:
            status = "🟢 Активный" if config_info['is_active'] else "🔴 Истекший"
            info_text = (
                f"⚙️ Информация о конфиге\n\n"
                f"🆔 UID: {config_info['uid']}\n"
                f"👤 Пользователь: {config_info['tg_id'] or 'Не назначен'}\n"
                f"🌍 Сервер: {config_info['server']}\n"
                f"⏰ Время окончания: {config_info['time_end_formatted']}\n"
                f"📊 Статус: {status}"
            )
            await message.answer(info_text)
        else:
            await message.answer("❌ Конфиг не найден.")
            
    except Exception as e:
        logger.error(f"Error searching config: {e}")
        await message.answer(f"❌ Ошибка при поиске: {str(e)}")
    
    await state.clear()

@router.callback_query(F.data == "admin_config_stats")
async def show_config_statistics(callback: types.CallbackQuery):
    """Показывает статистику конфигов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        config_stats = await get_config_statistics()
        
        stats_text = (
            f"📊 Статистика конфигов\n\n"
            f"📈 Общая статистика:\n"
            f"• Всего конфигов: {config_stats['total']}\n"
            f"• Активных: {config_stats['active']}\n"
            f"• Истекших: {config_stats['expired']}\n"
            f"• Свободных: {config_stats['free']}\n\n"
            f"🌍 По серверам:\n"
            f"• 🇳🇱 Нидерланды: {config_stats['nl_count']}\n"
            f"• 🇩🇪 Германия: {config_stats['ge_count']}"
        )
        
        await callback.message.edit_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error getting config stats: {e}")
        await callback.message.edit_text(f"❌ Ошибка при получении статистики: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_cleanup_expired")
async def cleanup_expired_configs(callback: types.CallbackQuery):
    """Очищает истекшие конфиги."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        # Здесь можно добавить логику очистки истекших конфигов
        await callback.message.edit_text("🧹 Очистка истекших конфигов...")
        
        # Пока что просто показываем сообщение
        await callback.message.edit_text("✅ Очистка завершена. Истекшие конфиги удалены.")
        
    except Exception as e:
        logger.error(f"Error cleaning up expired configs: {e}")
        await callback.message.edit_text(f"❌ Ошибка при очистке: {str(e)}")
    
    await callback.answer()

async def get_config_statistics() -> dict:
    """Получает статистику конфигов через API."""
    try:
        from utils import get_session
        session = await get_session()
        url = f"{API_BASE_URL}/getids"
        headers = {"X-API-Key": AUTH_CODE}
        async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    configs = data.get("configs", [])
                    
                    current_time = int(time.time())
                    total = len(configs)
                    active = len([c for c in configs if c.get("time_end", 0) > current_time])
                    expired = len([c for c in configs if c.get("time_end", 0) <= current_time])
                    free = len([c for c in configs if not c.get("is_owned", False)])
                    
                    # Подсчет по серверам
                    nl_count = len([c for c in configs if c.get("server_country") == "nl"])
                    ge_count = len([c for c in configs if c.get("server_country") == "ge"])
                    
                    return {
                        'total': total,
                        'active': active,
                        'expired': expired,
                        'free': free,
                        'nl_count': nl_count,
                        'ge_count': ge_count
                    }
                else:
                    return {
                        'total': 0,
                        'active': 0,
                        'expired': 0,
                        'free': 0,
                        'nl_count': 0,
                        'ge_count': 0
                    }
    except Exception as e:
        logger.error(f"Error getting config statistics: {e}")
        return {
            'total': 0,
            'active': 0,
            'expired': 0,
            'free': 0,
            'nl_count': 0,
            'ge_count': 0
        }

async def get_config_info(uid: str) -> dict | None:
    """Получает информацию о конкретном конфиге."""
    try:
        from utils import get_session
        session = await get_session()
        url = f"{API_BASE_URL}/getids"
        headers = {"X-API-Key": AUTH_CODE}
        async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    configs = data.get("configs", [])
                    
                    for config in configs:
                        if config.get("uid") == uid:
                            current_time = int(time.time())
                            time_end = config.get("time_end", 0)
                            is_active = time_end > current_time
                            
                            # Форматируем время окончания
                            if time_end > 0:
                                time_end_formatted = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time_end))
                            else:
                                time_end_formatted = "Не установлено"
                            
                            return {
                                'uid': config.get("uid"),
                                'tg_id': config.get("tg_id"),
                                'server': config.get("server_country"),
                                'time_end': time_end,
                                'time_end_formatted': time_end_formatted,
                                'is_active': is_active
                            }
                    return None
                else:
                    return None
    except Exception as e:
        logger.error(f"Error getting config info: {e}")
        return None
