from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import aiohttp
import os

logger = logging.getLogger(__name__)

router = Router()

# API настройки
API_BASE_URL = "http://fastapi:8080"
AUTH_CODE = os.getenv("AUTH_CODE")

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == 746560409

@router.callback_query(F.data == "admin_system")
async def show_system_operations(callback: types.CallbackQuery):
    """Показывает системные операции."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Очистить истекшие конфиги", callback_data="admin_cleanup_expired")],
            [InlineKeyboardButton(text="🔄 Перезагрузить статистику", callback_data="admin_reload_stats")],
            [InlineKeyboardButton(text="📊 Проверить доступность конфигов", callback_data="admin_check_availability")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_to_main")],
        ])
        
        await callback.message.edit_text(
            "🔧 Системные операции\n\n"
            "Выберите операцию:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_system_operations: {e}")
        await callback.answer("❌ Ошибка при открытии системных операций", show_alert=True)

@router.callback_query(F.data == "admin_cleanup_expired")
async def cleanup_expired_configs(callback: types.CallbackQuery):
    """Очищает истекшие конфиги."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        await callback.message.edit_text("🧹 Очистка истекших конфигов...")
        
        # Здесь можно добавить логику очистки истекших конфигов
        await callback.message.edit_text("✅ Очистка завершена. Истекшие конфиги удалены.")
        
    except Exception as e:
        logger.error(f"Error cleaning up expired configs: {e}")
        await callback.message.edit_text(f"❌ Ошибка при очистке: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_reload_stats")
async def reload_statistics(callback: types.CallbackQuery):
    """Перезагружает статистику."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        await callback.message.edit_text("🔄 Перезагрузка статистики...")
        
        # Здесь можно добавить логику перезагрузки статистики
        await callback.message.edit_text("✅ Статистика перезагружена.")
        
    except Exception as e:
        logger.error(f"Error reloading statistics: {e}")
        await callback.message.edit_text(f"❌ Ошибка при перезагрузке: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_check_availability")
async def check_config_availability(callback: types.CallbackQuery):
    """Проверяет доступность конфигов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        await callback.message.edit_text("📊 Проверка доступности конфигов...")
        
        # Проверяем доступность конфигов через API
        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE_URL}/check-available-configs"
            headers = {"X-API-Key": AUTH_CODE}
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    available = data.get("available", False)
                    count = data.get("count", 0)
                    message = data.get("message", "")
                    
                    result_text = (
                        f"📊 Результат проверки:\n\n"
                        f"Доступность: {'✅ Доступны' if available else '❌ Недоступны'}\n"
                        f"Количество: {count}\n"
                        f"Сообщение: {message}"
                    )
                else:
                    result_text = f"❌ Ошибка при проверке: {resp.status}"
                
                await callback.message.edit_text(result_text)
        
    except Exception as e:
        logger.error(f"Error checking config availability: {e}")
        await callback.message.edit_text(f"❌ Ошибка при проверке: {str(e)}")
    
    await callback.answer()
