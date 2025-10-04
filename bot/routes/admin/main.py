from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import time
from datetime import datetime
import aiohttp
import os
import asyncio
from keyboards import keyboard

logger = logging.getLogger(__name__)

router = Router()

# ID администратора
ADMIN_ID = 746560409

# API настройки
API_BASE_URL = "http://fastapi:8080"
AUTH_CODE = os.getenv("AUTH_CODE")

# Проверяем наличие AUTH_CODE (только предупреждение, не ошибка)
if not AUTH_CODE:
    logger.warning("AUTH_CODE environment variable is not set!")

class AdminStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_notification_type = State()
    waiting_for_user_search = State()
    waiting_for_config_uid = State()
    waiting_for_promo_message = State()

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_ID

@router.message(F.text == "🔧 Админ панель")
async def admin_panel(message: types.Message):
    """Показывает админ панель только для администратора."""
    try:
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет доступа к админ панели.", reply_markup=keyboard.create_keyboard())
            return
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💵 Доход (руб / звезды)", callback_data="admin_revenue")],
            [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="⚙️ Управление конфигами", callback_data="admin_configs")],
            [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="admin_detailed_stats")],
            [InlineKeyboardButton(text="🔧 Системные операции", callback_data="admin_system")],
            [InlineKeyboardButton(text="🔔 Уведомления о подписке", callback_data="admin_notifications")],
        ])
        
        await message.answer(
            "🔧 <b>Админ панель</b>\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in admin_panel: {e}")
        await message.answer("Произошла ошибка при открытии админ панели.", reply_markup=keyboard.create_keyboard())

@router.callback_query(F.data == "back_to_admin_panel")
async def back_to_admin_panel(callback: types.CallbackQuery):
    """Возврат к главному меню админки."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💵 Доход (руб / звезды)", callback_data="admin_revenue")],
            [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="⚙️ Управление конфигами", callback_data="admin_configs")],
            [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="admin_detailed_stats")],
            [InlineKeyboardButton(text="🔧 Системные операции", callback_data="admin_system")],
            [InlineKeyboardButton(text="🔔 Уведомления о подписке", callback_data="admin_notifications")],
        ])
        
        await callback.message.edit_text(
            "🔧 <b>Админ панель</b>\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in back_to_admin_panel: {e}")
        await callback.answer("Произошла ошибка при возврате к админ панели.")

@router.callback_query(F.data == "back_to_main_admin")
async def back_to_main_admin(callback: types.CallbackQuery):
    """Возврат к главному меню админки."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💵 Доход (руб / звезды)", callback_data="admin_revenue")],
            [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="⚙️ Управление конфигами", callback_data="admin_configs")],
            [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="admin_detailed_stats")],
            [InlineKeyboardButton(text="🔧 Системные операции", callback_data="admin_system")],
            [InlineKeyboardButton(text="🔔 Уведомления о подписке", callback_data="admin_notifications")],
        ])
        
        await callback.message.edit_text(
            "🔧 <b>Админ панель</b>\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in back_to_main_admin: {e}")
        await callback.answer("Произошла ошибка при возврате к админ панели.")

@router.callback_query(F.data == "admin_back_to_main")
async def admin_back_to_main(callback: types.CallbackQuery):
    """Возврат к главному меню админки."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💵 Доход (руб / звезды)", callback_data="admin_revenue")],
            [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="⚙️ Управление конфигами", callback_data="admin_configs")],
            [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="admin_detailed_stats")],
            [InlineKeyboardButton(text="🔧 Системные операции", callback_data="admin_system")],
            [InlineKeyboardButton(text="🔔 Уведомления о подписке", callback_data="admin_notifications")],
        ])
        
        await callback.message.edit_text(
            "🔧 <b>Админ панель</b>\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_back_to_main: {e}")
        await callback.answer("Произошла ошибка при возврате к админ панели.")

@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: types.CallbackQuery):
    """Возврат к главному меню админки через callback."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💵 Доход (руб / звезды)", callback_data="admin_revenue")],
            [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="⚙️ Управление конфигами", callback_data="admin_configs")],
            [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="admin_detailed_stats")],
            [InlineKeyboardButton(text="🔧 Системные операции", callback_data="admin_system")],
            [InlineKeyboardButton(text="🔔 Уведомления о подписке", callback_data="admin_notifications")],
        ])
        
        await callback.message.edit_text(
            "🔧 <b>Админ панель</b>\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_panel_callback: {e}")
        await callback.answer("Произошла ошибка при возврате к админ панели.")
