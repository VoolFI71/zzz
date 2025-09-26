from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import time
import aiohttp
import os

logger = logging.getLogger(__name__)

router = Router()

# ID администратора
ADMIN_ID = 746560409

# API настройки
API_BASE_URL = "http://fastapi:8080"
AUTH_CODE = os.getenv("AUTH_CODE")

# Проверяем наличие AUTH_CODE
if not AUTH_CODE:
    logger.error("AUTH_CODE environment variable is not set!")
    raise ValueError("AUTH_CODE environment variable is required")

class AdminStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_user_search = State()
    waiting_for_config_uid = State()

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_ID

@router.message(F.text == "🔧 Админ панель")
async def admin_panel(message: types.Message):
    """Показывает админ панель только для администратора."""
    try:
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет доступа к админ панели.")
            return
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="⚙️ Управление конфигами", callback_data="admin_configs")],
            [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="admin_detailed_stats")],
            [InlineKeyboardButton(text="🔧 Системные операции", callback_data="admin_system")],
        ])
        
        await message.answer(
            "🔧 Админ панель\n\n"
            "Выберите действие:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error in admin_panel: {e}")
        await message.answer("❌ Ошибка при открытии админ панели.")

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс отправки сообщения всем пользователям."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        
        await callback.message.edit_text(
            "📢 Отправка сообщения всем пользователям\n\n"
            "Введите сообщение, которое хотите отправить всем пользователям:"
        )
        await state.set_state(AdminStates.waiting_for_message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in start_broadcast: {e}")
        await callback.answer("❌ Ошибка при запуске рассылки", show_alert=True)

@router.message(AdminStates.waiting_for_message)
async def process_broadcast_message(message: types.Message, state: FSMContext, bot):
    """Обрабатывает сообщение для рассылки и отправляет его всем пользователям."""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа.")
        await state.clear()
        return
    
    broadcast_text = message.text
    if not broadcast_text or len(broadcast_text.strip()) == 0:
        await message.answer("Сообщение не может быть пустым. Попробуйте снова:")
        return
    
    # Получаем список всех пользователей из БД
    try:
        user_ids = await get_all_user_ids()
        if not user_ids:
            await message.answer("В базе данных нет пользователей.")
            await state.clear()
            return
        
        # Отправляем сообщение администратору о начале рассылки
        await message.answer(f"📤 Начинаю рассылку сообщения {len(user_ids)} пользователям...")
        
        # Отправляем сообщение всем пользователям
        sent_count = 0
        failed_count = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, broadcast_text)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send message to user {user_id}: {e}")
                failed_count += 1
        
        # Отправляем отчет администратору
        await message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"📊 Статистика:\n"
            f"• Отправлено: {sent_count}\n"
            f"• Ошибок: {failed_count}\n"
            f"• Всего пользователей: {len(user_ids)}"
        )
        
    except Exception as e:
        logger.error(f"Error during broadcast: {e}")
        await message.answer(f"❌ Ошибка при рассылке: {str(e)}")
    
    await state.clear()

@router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: types.CallbackQuery):
    """Показывает статистику пользователей."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        stats = await get_user_stats()
        stats_text = (
            f"📊 Статистика пользователей\n\n"
            f"👥 Всего пользователей: {stats['total_users']}\n"
            f"🎁 Использовали пробную подписку: {stats['trial_used']}\n"
            f"💰 Имеют баланс дней: {stats['with_balance']}\n"
            f"🤝 Общее количество рефералов: {stats['total_referrals']}"
        )
        
        await callback.message.edit_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await callback.message.edit_text(f"❌ Ошибка при получении статистики: {str(e)}")
    
    await callback.answer()

async def get_all_user_ids() -> list[str]:
    """Получает список всех tg_id через API."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"X-API-Key": AUTH_CODE}
            
            # Получаем все конфиги и извлекаем уникальных пользователей
            async with session.get(f"{API_BASE_URL}/all-configs", headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"API error getting all configs: {resp.status}")
                    return []
                
                data = await resp.json()
                configs = data.get('configs', [])
                
                # Извлекаем уникальных пользователей
                user_ids = set()
                for config in configs:
                    tg_id = config.get('tg_id')
                    if tg_id and tg_id.strip():
                        user_ids.add(tg_id)
                
                return list(user_ids)
    except Exception as e:
        logger.error(f"Error getting user IDs: {e}")
        return []

async def get_user_stats() -> dict:
    """Получает статистику пользователей через API."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"X-API-Key": AUTH_CODE}
            
            # Получаем все конфиги для анализа
            async with session.get(f"{API_BASE_URL}/all-configs", headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"API error getting all configs: {resp.status}")
                    return {
                        'total_users': 0,
                        'trial_used': 0,
                        'with_balance': 0,
                        'total_referrals': 0
                    }
                
                data = await resp.json()
                configs = data.get('configs', [])
                
                # Анализируем конфиги для получения статистики пользователей
                user_ids = set()
                for config in configs:
                    tg_id = config.get('tg_id')
                    if tg_id and tg_id.strip():
                        user_ids.add(tg_id)
                
                total_users = len(user_ids)
                
                # Пока что возвращаем заглушки для полей, которых нет в API
                return {
                    'total_users': total_users,
                    'trial_used': 0,  # Нужно добавить в API
                    'with_balance': 0,  # Нужно добавить в API
                    'total_referrals': 0  # Нужно добавить в API
                }
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {
            'total_users': 0,
            'trial_used': 0,
            'with_balance': 0,
            'total_referrals': 0
        }

# Новые функции админ панели

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
                f"📅 Дата регистрации: {user_info['created_at']}\n"
                f"🔗 Активных конфигов: {user_info['active_configs']}"
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
            f"• FI сервер: {config_stats['fi_count']}\n"
            f"• NL сервер: {config_stats['nl_count']}"
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

@router.callback_query(F.data == "admin_detailed_stats")
async def show_detailed_stats(callback: types.CallbackQuery):
    """Показывает детальную статистику."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        detailed_stats = await get_detailed_statistics()
        
        stats_text = (
            f"📈 Детальная статистика\n\n"
            f"👥 Пользователи:\n"
            f"• Всего: {detailed_stats['users']['total']}\n"
            f"• Активных: {detailed_stats['users']['active']}\n"
            f"• С пробной подпиской: {detailed_stats['users']['trial_used']}\n"
            f"• С балансом: {detailed_stats['users']['with_balance']}\n\n"
            f"⚙️ Конфиги:\n"
            f"• Всего: {detailed_stats['configs']['total']}\n"
            f"• Активных: {detailed_stats['configs']['active']}\n"
            f"• Истекших: {detailed_stats['configs']['expired']}\n"
            f"• FI сервер: {detailed_stats['configs']['fi']}\n"
            f"• NL сервер: {detailed_stats['configs']['nl']}\n\n"
            f"🤝 Рефералы:\n"
            f"• Общее количество: {detailed_stats['referrals']['total']}\n"
            f"• Топ реферер: {detailed_stats['referrals']['top_referrer']}"
        )
        
        await callback.message.edit_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error getting detailed stats: {e}")
        await callback.message.edit_text(f"❌ Ошибка при получении статистики: {str(e)}")
    
    await callback.answer()

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

@router.callback_query(F.data == "admin_back_to_main")
async def back_to_main_admin(callback: types.CallbackQuery):
    """Возвращает к главному меню админ панели."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="⚙️ Управление конфигами", callback_data="admin_configs")],
            [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="admin_detailed_stats")],
            [InlineKeyboardButton(text="🔧 Системные операции", callback_data="admin_system")],
        ])
        
        await callback.message.edit_text(
            "🔧 Админ панель\n\n"
            "Выберите действие:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in back_to_main_admin: {e}")
        await callback.answer("❌ Ошибка при возврате в главное меню", show_alert=True)

# Вспомогательные функции для новых возможностей

async def get_user_info(tg_id: int) -> dict | None:
    """Получает информацию о пользователе через API."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            headers = {"X-API-Key": AUTH_CODE}
            
            # Получаем конфиги пользователя
            async with session.get(f"{API_BASE_URL}/usercodes/{tg_id}", headers=headers) as resp:
                if resp.status == 404:
                    return None
                elif resp.status != 200:
                    logger.error(f"API error getting user configs: {resp.status}")
                    return None
                
                try:
                    configs = await resp.json()
                except aiohttp.ContentTypeError as e:
                    logger.error(f"Invalid JSON response: {e}")
                    return None
                
                active_configs = len([c for c in configs if c.get('time_end', 0) > int(time.time())])
                
                # Базовая информация (пока что используем данные из конфигов)
                return {
                    'tg_id': str(tg_id),
                    'trial_used': False,  # Нужно добавить в API
                    'balance': 0,  # Нужно добавить в API
                    'referral_count': 0,  # Нужно добавить в API
                    'created_at': 'Неизвестно',  # Нужно добавить в API
                    'active_configs': active_configs
                }
    except aiohttp.ClientError as e:
        logger.error(f"Network error getting user info: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return None

async def get_config_statistics() -> dict:
    """Получает статистику конфигов через API."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            headers = {"X-API-Key": AUTH_CODE}
            
            # Получаем все конфиги
            async with session.get(f"{API_BASE_URL}/all-configs", headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"API error getting all configs: {resp.status}")
                    return {
                        'total': 0, 'active': 0, 'expired': 0, 'free': 0,
                        'fi_count': 0, 'nl_count': 0
                    }
                
                try:
                    data = await resp.json()
                except aiohttp.ContentTypeError as e:
                    logger.error(f"Invalid JSON response: {e}")
                    return {
                        'total': 0, 'active': 0, 'expired': 0, 'free': 0,
                        'fi_count': 0, 'nl_count': 0
                    }
                
                configs = data.get('configs', [])
                
                current_time = int(time.time())
                total = len(configs)
                active = len([c for c in configs if c.get('time_end', 0) > current_time])
                expired = len([c for c in configs if c.get('time_end', 0) <= current_time and c.get('time_end', 0) > 0])
                free = len([c for c in configs if c.get('time_end', 0) == 0])
                fi_count = len([c for c in configs if c.get('server_country') == 'fi'])
                nl_count = len([c for c in configs if c.get('server_country') == 'nl'])
                
                return {
                    'total': total,
                    'active': active,
                    'expired': expired,
                    'free': free,
                    'fi_count': fi_count,
                    'nl_count': nl_count
                }
    except aiohttp.ClientError as e:
        logger.error(f"Network error getting config statistics: {e}")
        return {
            'total': 0, 'active': 0, 'expired': 0, 'free': 0,
            'fi_count': 0, 'nl_count': 0
        }
    except Exception as e:
        logger.error(f"Error getting config statistics: {e}")
        return {
            'total': 0, 'active': 0, 'expired': 0, 'free': 0,
            'fi_count': 0, 'nl_count': 0
        }

async def get_config_info(uid: str) -> dict | None:
    """Получает информацию о конфиге через API."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            headers = {"X-API-Key": AUTH_CODE}
            
            # Получаем все конфиги и ищем нужный
            async with session.get(f"{API_BASE_URL}/all-configs", headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"API error getting all configs: {resp.status}")
                    return None
                
                try:
                    data = await resp.json()
                except aiohttp.ContentTypeError as e:
                    logger.error(f"Invalid JSON response: {e}")
                    return None
                
                configs = data.get('configs', [])
                
                # Ищем конфиг по UID
                config = next((c for c in configs if c.get('uid') == uid), None)
                if not config:
                    return None
                
                current_time = int(time.time())
                time_end = config.get('time_end', 0)
                is_active = time_end > current_time
                
                # Форматируем время
                if time_end == 0:
                    time_end_formatted = "Не установлено"
                else:
                    from datetime import datetime
                    time_end_formatted = datetime.fromtimestamp(time_end).strftime("%d.%m.%Y %H:%M")
                
                return {
                    'uid': config.get('uid'),
                    'tg_id': config.get('tg_id'),
                    'time_end': time_end,
                    'time_end_formatted': time_end_formatted,
                    'server': config.get('server_country'),
                    'is_active': is_active
                }
    except aiohttp.ClientError as e:
        logger.error(f"Network error getting config info: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting config info: {e}")
        return None

async def get_detailed_statistics() -> dict:
    """Получает детальную статистику через API."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            headers = {"X-API-Key": AUTH_CODE}
            
            # Получаем все конфиги
            async with session.get(f"{API_BASE_URL}/all-configs", headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"API error getting all configs: {resp.status}")
                    return {
                        'users': {'total': 0, 'active': 0, 'trial_used': 0, 'with_balance': 0},
                        'configs': {'total': 0, 'active': 0, 'expired': 0, 'fi': 0, 'nl': 0},
                        'referrals': {'total': 0, 'top_referrer': 'Нет данных'}
                    }
                
                try:
                    data = await resp.json()
                except aiohttp.ContentTypeError as e:
                    logger.error(f"Invalid JSON response: {e}")
                    return {
                        'users': {'total': 0, 'active': 0, 'trial_used': 0, 'with_balance': 0},
                        'configs': {'total': 0, 'active': 0, 'expired': 0, 'fi': 0, 'nl': 0},
                        'referrals': {'total': 0, 'top_referrer': 'Нет данных'}
                    }
                
                configs = data.get('configs', [])
                
                current_time = int(time.time())
                
                # Анализируем конфиги для получения статистики
                total_configs = len(configs)
                active_configs = len([c for c in configs if c.get('time_end', 0) > current_time])
                expired_configs = len([c for c in configs if c.get('time_end', 0) <= current_time and c.get('time_end', 0) > 0])
                fi_configs = len([c for c in configs if c.get('server_country') == 'fi'])
                nl_configs = len([c for c in configs if c.get('server_country') == 'nl'])
                
                # Получаем уникальных пользователей
                user_ids = set()
                active_user_ids = set()
                for config in configs:
                    tg_id = config.get('tg_id')
                    if tg_id and tg_id.strip():
                        user_ids.add(tg_id)
                        if config.get('time_end', 0) > current_time:
                            active_user_ids.add(tg_id)
                
                total_users = len(user_ids)
                active_users = len(active_user_ids)
                
                return {
                    'users': {
                        'total': total_users,
                        'active': active_users,
                        'trial_used': 0,  # Нужно добавить в API
                        'with_balance': 0  # Нужно добавить в API
                    },
                    'configs': {
                        'total': total_configs,
                        'active': active_configs,
                        'expired': expired_configs,
                        'fi': fi_configs,
                        'nl': nl_configs
                    },
                    'referrals': {
                        'total': 0,  # Нужно добавить в API
                        'top_referrer': 'Нет данных'  # Нужно добавить в API
                    }
                }
    except aiohttp.ClientError as e:
        logger.error(f"Network error getting detailed statistics: {e}")
        return {
            'users': {'total': 0, 'active': 0, 'trial_used': 0, 'with_balance': 0},
            'configs': {'total': 0, 'active': 0, 'expired': 0, 'fi': 0, 'nl': 0},
            'referrals': {'total': 0, 'top_referrer': 'Нет данных'}
        }
    except Exception as e:
        logger.error(f"Error getting detailed statistics: {e}")
        return {
            'users': {'total': 0, 'active': 0, 'trial_used': 0, 'with_balance': 0},
            'configs': {'total': 0, 'active': 0, 'expired': 0, 'fi': 0, 'nl': 0},
            'referrals': {'total': 0, 'top_referrer': 'Нет данных'}
        }

# Дополнительные системные операции

@router.callback_query(F.data == "admin_cleanup_expired")
async def cleanup_expired_configs(callback: types.CallbackQuery):
    """Очищает истекшие конфиги через API."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        # Используем API для очистки истекших конфигов
        async with aiohttp.ClientSession() as session:
            headers = {"X-API-Key": AUTH_CODE}
            
            # Пока что просто показываем сообщение, так как API эндпоинт для очистки не реализован
            await callback.message.edit_text(
                f"🧹 Очистка истекших конфигов\n\n"
                f"⚠️ Функция очистки временно недоступна\n\n"
                f"Истекшие конфиги автоматически становятся доступными для повторного использования."
            )
        
    except Exception as e:
        logger.error(f"Error cleaning expired configs: {e}")
        await callback.message.edit_text(f"❌ Ошибка при очистке: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_reload_stats")
async def reload_statistics(callback: types.CallbackQuery):
    """Перезагружает статистику."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        # Получаем свежую статистику
        stats = await get_user_stats()
        config_stats = await get_config_statistics()
        
        stats_text = (
            f"🔄 Обновленная статистика\n\n"
            f"👥 Пользователи:\n"
            f"• Всего: {stats['total_users']}\n"
            f"• Использовали пробную: {stats['trial_used']}\n"
            f"• С балансом: {stats['with_balance']}\n"
            f"• Рефералов: {stats['total_referrals']}\n\n"
            f"⚙️ Конфиги:\n"
            f"• Всего: {config_stats['total']}\n"
            f"• Активных: {config_stats['active']}\n"
            f"• Истекших: {config_stats['expired']}\n"
            f"• Свободных: {config_stats['free']}\n"
            f"• FI: {config_stats['fi_count']}\n"
            f"• NL: {config_stats['nl_count']}"
        )
        
        await callback.message.edit_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error reloading stats: {e}")
        await callback.message.edit_text(f"❌ Ошибка при обновлении: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_check_availability")
async def check_config_availability(callback: types.CallbackQuery):
    """Проверяет доступность конфигов на серверах через API."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            headers = {"X-API-Key": AUTH_CODE}
            
            # Проверяем доступность для каждого сервера
            fi_available = False
            nl_available = False
            any_available = False
            
            try:
                # Проверяем FI сервер
                async with session.get(f"{API_BASE_URL}/check-available-configs?server=fi", headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            data = await resp.json()
                            fi_available = data.get('available', False)
                        except aiohttp.ContentTypeError:
                            logger.error("Invalid JSON response from FI server check")
                    else:
                        logger.error(f"FI server check failed with status: {resp.status}")
            except aiohttp.ClientError as e:
                logger.error(f"Network error checking FI server: {e}")
            
            try:
                # Проверяем NL сервер
                async with session.get(f"{API_BASE_URL}/check-available-configs?server=nl", headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            data = await resp.json()
                            nl_available = data.get('available', False)
                        except aiohttp.ContentTypeError:
                            logger.error("Invalid JSON response from NL server check")
                    else:
                        logger.error(f"NL server check failed with status: {resp.status}")
            except aiohttp.ClientError as e:
                logger.error(f"Network error checking NL server: {e}")
            
            try:
                # Проверяем общую доступность
                async with session.get(f"{API_BASE_URL}/check-available-configs", headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            data = await resp.json()
                            any_available = data.get('available', False)
                        except aiohttp.ContentTypeError:
                            logger.error("Invalid JSON response from general availability check")
                            any_available = fi_available or nl_available
                    else:
                        logger.error(f"General availability check failed with status: {resp.status}")
                        any_available = fi_available or nl_available
            except aiohttp.ClientError as e:
                logger.error(f"Network error checking general availability: {e}")
                any_available = fi_available or nl_available
            
            availability_text = (
                f"📊 Проверка доступности конфигов\n\n"
                f"🇫🇮 Финляндия: {'✅ Доступны' if fi_available else '❌ Нет свободных'}\n"
                f"🇳🇱 Нидерланды: {'✅ Доступны' if nl_available else '❌ Нет свободных'}\n"
                f"🌍 Общая доступность: {'✅ Есть конфиги' if any_available else '❌ Нет конфигов'}\n\n"
                f"💡 Рекомендация: {'Создать новые конфиги' if not any_available else 'Система работает нормально'}"
            )
            
            await callback.message.edit_text(availability_text)
        
    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        await callback.message.edit_text(f"❌ Ошибка при проверке: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_config_stats")
async def show_config_statistics(callback: types.CallbackQuery):
    """Показывает детальную статистику конфигов."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        
        config_stats = await get_config_statistics()
        
        # Дополнительная статистика по времени
        current_time = int(time.time())
        tomorrow = current_time + 86400
        week = current_time + 604800
        
        # Анализируем конфиги для получения временной статистики
        expiring_soon = 0
        expiring_week = 0
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                headers = {"X-API-Key": AUTH_CODE}
                async with session.get(f"{API_BASE_URL}/all-configs", headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            data = await resp.json()
                            configs = data.get('configs', [])
                            
                            # Конфиги, истекающие в ближайшие 24 часа
                            expiring_soon = len([c for c in configs if current_time < c.get('time_end', 0) <= tomorrow])
                            
                            # Конфиги, истекающие в ближайшие 7 дней
                            expiring_week = len([c for c in configs if current_time < c.get('time_end', 0) <= week])
                        except aiohttp.ContentTypeError as e:
                            logger.error(f"Invalid JSON response in config stats: {e}")
                    else:
                        logger.error(f"API error getting configs for stats: {resp.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Network error getting config stats: {e}")
        except Exception as e:
            logger.error(f"Error getting config stats: {e}")
        
        stats_text = (
            f"📊 Детальная статистика конфигов\n\n"
            f"📈 Общая статистика:\n"
            f"• Всего конфигов: {config_stats['total']}\n"
            f"• Активных: {config_stats['active']}\n"
            f"• Истекших: {config_stats['expired']}\n"
            f"• Свободных: {config_stats['free']}\n\n"
            f"🌍 По серверам:\n"
            f"• 🇫🇮 Финляндия: {config_stats['fi_count']}\n"
            f"• 🇳🇱 Нидерланды: {config_stats['nl_count']}\n\n"
            f"⏰ Истекающие:\n"
            f"• В ближайшие 24 часа: {expiring_soon}\n"
            f"• В ближайшие 7 дней: {expiring_week}\n\n"
            f"📊 Использование: {round((config_stats['active'] / config_stats['total']) * 100, 1) if config_stats['total'] > 0 else 0}%"
        )
        
        await callback.message.edit_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error getting config stats: {e}")
        await callback.message.edit_text(f"❌ Ошибка при получении статистики: {str(e)}")
    
    await callback.answer()
