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
            await message.answer("У вас нет доступа к админ панели.")
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
            "🔧 Админ панель\n\n"
            "Выберите действие:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error in admin_panel: {e}")
        await message.answer("❌ Ошибка при открытии админ панели.")

@router.callback_query(F.data == "notif")
async def send_notif(callback: types.CallbackQuery, bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.answer()  # убрать "часики" у клиента

    url = f"{API_BASE_URL}/expiring-users"
    headers = {"X-API-Key": AUTH_CODE}
            
    # Получаем пользователей с истекающими подписками
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"/expiring-users returned {resp.status}: {text}")
                    await callback.message.answer(f"Ошибка запроса: {resp.status}")
                    return
                data = await resp.json()
    except Exception as e:
        logger.error(f"Error fetching /expiring-users: {e}")
        await callback.message.answer(f"Ошибка при подключении к серверу: {e}")
        return

    if not data:
        await callback.message.answer("Нет пользователей с подпиской, истекающей в ближайшие 8 часов.")
        return

    sent = 0
    failed = 0
    invalid = 0

    now = int(time.time())

    for item in data:
        tg = item.get("tg_id")
        te = item.get("time_end")
        if not tg or te is None:
            invalid += 1
            continue

        try:
            te = int(te)
        except (TypeError, ValueError):
            invalid += 1
            continue

        # вычисляем оставшиеся секунды/минуты
        remaining_sec = te - now
        if remaining_sec < 0:
            # если уже просрочено — можно пропустить или уведомить как "уже истекло"
            text = "Ваша подписка на конфиг уже истекла."
        else:
            minutes = remaining_sec // 60
            # округление вверх для отображения "осталось N минут"
            if remaining_sec % 60:
                minutes += 1
            text = f"🔔 Внимание! Подписка на ваш конфиг истекает через {minutes} минут."

        try:
            await bot.send_message(int(tg), text)
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send notif to {tg}: {e}")
            failed += 1

        # небольшая пауза, чтобы не превышать лимиты
        await asyncio.sleep(0.05)  # 50ms, увеличьте при необходимости

    summary = (
        f"Уведомления отправлены.\n\n"
        f"Отправлено: {sent}\n"
        f"Не доставлено (ошибки): {failed}\n"
        f"Пропущено (некорректные записи): {invalid}\n"
        f"Всего проверено записей: {len(data)}"
    )
    await callback.message.answer(summary)

@router.callback_query(F.data == "admin_notifications")
async def notifications_menu(callback: types.CallbackQuery):
    """Меню различных типов уведомлений для увеличения продаж."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Уведомление об окончании подписки", callback_data="notif")],
        [InlineKeyboardButton(text="🎯 Пользователи без подписки (привлечение)", callback_data="notif_no_sub")],
        [InlineKeyboardButton(text="🧪 Только пробная, без покупок", callback_data="notif_trial_only")],
        [InlineKeyboardButton(text="💎 Пользователи с истекшей подпиской (возврат)", callback_data="notif_expired")],
        [InlineKeyboardButton(text="🔥 Акция/скидка", callback_data="notif_promo")],
        # [InlineKeyboardButton(text="📢 Новые функции/обновления", callback_data="notif_features")],
        # [InlineKeyboardButton(text="💡 Напоминание о преимуществах", callback_data="notif_benefits")],
        [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_panel")],
    ])
    
    await callback.message.edit_text(
        "🔔 Уведомления для увеличения продаж\n\n"
        "Выберите тип рассылки:",
        reply_markup=keyboard
    )
    await callback.answer()
@router.callback_query(F.data == "admin_revenue")
async def show_revenue(callback: types.CallbackQuery):
    """Показывает суммарные агрегаты оплат: рубли и звёзды."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    try:
        from database import db as _db
        aggr = await _db.get_payments_aggregates()
        total_rub = aggr.get("total_rub", 0)
        total_stars = aggr.get("total_stars", 0)
        count_rub = aggr.get("count_rub", 0)
        count_stars = aggr.get("count_stars", 0)

        text = (
            "💵 Доход сервиса\n\n"
            f"Рубли: {total_rub} ₽ (платежей: {count_rub})\n"
            f"Звёзды: {total_stars} ⭐ (платежей: {count_stars})\n\n"
            "Примечание: суммы рассчитываются по актуальным настройкам цен на момент оплаты."
        )
        await callback.message.edit_text(text)
    except Exception as e:
        logger.error(f"Error showing revenue: {e}")
        await callback.message.edit_text("❌ Не удалось получить данные о доходе")
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
async def back_to_admin_panel(callback: types.CallbackQuery):
    """Возврат в главное меню админ панели."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
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
    
    await callback.message.edit_text(
        "🔧 Админ панель\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "notif_no_sub")
async def send_no_sub_notification(callback: types.CallbackQuery, bot):
    """Отправляет уведомления пользователям без подписки."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.answer()
    
    # Получаем пользователей без подписки
    try:
        user_ids = await get_users_without_any_subscription()
        if not user_ids:
            await callback.message.answer("Нет пользователей без подписки.")
            return
        
        message_text = (
            "🚀 Привет! 👋\n\n"
            "У вас ещё нет активной подписки на наш VPN-сервис.\n\n"
            "🔒 Получите полный доступ к:\n"
            "• Безопасному интернету\n"
            "• Обходу блокировок\n"
            "• Защите личных данных\n"
            "• Высокой скорости соединения\n\n"
            "🎁 Попробуйте прямо сейчас — первые 3 дня бесплатно!\n\n"
            "Нажмите /start для оформления подписки."
        )
        
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, message_text)
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send no-sub notification to {user_id}: {e}")
                failed += 1
            await asyncio.sleep(0.05)
        
        await callback.message.answer(
            f"✅ Рассылка пользователям без подписки завершена!\n\n"
            f"📊 Статистика:\n"
            f"• Отправлено: {sent}\n"
            f"• Ошибок: {failed}\n"
            f"• Всего пользователей: {len(user_ids)}"
        )
        
    except Exception as e:
        logger.error(f"Error in send_no_sub_notification: {e}")
        await callback.message.answer(f"❌ Ошибка при рассылке: {str(e)}")

@router.callback_query(F.data == "notif_expired")
async def send_expired_notification(callback: types.CallbackQuery, bot):
    """Отправляет уведомления пользователям с истекшей подпиской."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.answer()
    
    # Получаем пользователей с истекшей подпиской
    try:
        # Получаем всех пользователей из bot БД
        all_bot_users = await get_all_user_ids()
        
        # Получаем пользователей с активной подпиской из FastAPI
        active_sub_users = await get_users_with_active_subscription()
        
        # Пользователи с истекшей подпиской = есть в bot БД, но нет в активных подписках
        # И при этом использовали пробную подписку или имели баланс
        user_ids = []
        for user_id in all_bot_users:
            if user_id not in active_sub_users:
                # Проверяем, использовал ли пользователь пробную подписку или имел баланс
                import aiosqlite
                async with aiosqlite.connect("users.db") as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT trial_3d_used, balance FROM users WHERE tg_id = ?
                        """, (user_id,))
                        row = await cursor.fetchone()
                        if row and (row[0] == 1 or row[1] > 0):
                            user_ids.append(user_id)
        
        if not user_ids:
            await callback.message.answer("Нет пользователей с истекшей подпиской.")
            return
        
        message_text = (
            "🔄 Мы скучаем! 😊\n\n"
            "Ваша подписка сейчас не активна, но мы подготовили для вас:\n\n"
            "• ♾️ Безлимитный трафик для мобильного интернета (если в тарифе есть опция на безлимитные соцсети, например VK)\n"
            "• 🎁 Бонусные дни при продлении\n"
            "• 🛟 Поддержка 24/7\n\n"
            "Важно: если у вас МТС, ЙОТА или ТЕЛЕ2 — то с нашим VPN вы сможете пользоваться мобильным интернетом даже там, где его отключают.\n\n"
        )
        
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, message_text)
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send expired notification to {user_id}: {e}")
                failed += 1
            await asyncio.sleep(0.05)
        
        await callback.message.answer(
            f"✅ Рассылка пользователям с истекшей подпиской завершена!\n\n"
            f"📊 Статистика:\n"
            f"• Отправлено: {sent}\n"
            f"• Ошибок: {failed}\n"
            f"• Всего пользователей: {len(user_ids)}"
        )
        
    except Exception as e:
        logger.error(f"Error in send_expired_notification: {e}")
        await callback.message.answer(f"❌ Ошибка при рассылке: {str(e)}")

@router.callback_query(F.data == "notif_promo")
async def send_promo_notification(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс отправки промо-уведомления."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔥 Промо-рассылка\n\n"
        "Введите текст акции/скидки, который хотите отправить пользователям:"
    )
    await state.set_state(AdminStates.waiting_for_promo_message)
    await callback.answer()

@router.callback_query(F.data == "notif_features")
async def send_features_notification(callback: types.CallbackQuery, bot):
    """Отправляет уведомления о новых функциях."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        user_ids = await get_all_user_ids()
        if not user_ids:
            await callback.message.answer("В базе данных нет пользователей.")
            return
        
        message_text = (
            "🆕 Обновление сервиса! 🎉\n\n"
            "Мы добавили новые возможности:\n\n"
            "✨ Что нового:\n"
            "• Улучшенная скорость соединения\n"
            "• Новые серверы в разных странах\n"
            "• Обновленный интерфейс\n"
            "• Расширенная техподдержка\n\n"
            "🚀 Обновите приложение и наслаждайтесь улучшениями!\n\n"
            "Спасибо, что остаетесь с нами! 💙"
        )
        
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, message_text)
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send features notification to {user_id}: {e}")
                failed += 1
            await asyncio.sleep(0.05)
        
        await callback.message.answer(
            f"✅ Рассылка о новых функциях завершена!\n\n"
            f"📊 Статистика:\n"
            f"• Отправлено: {sent}\n"
            f"• Ошибок: {failed}\n"
            f"• Всего пользователей: {len(user_ids)}"
        )
        
    except Exception as e:
        logger.error(f"Error in send_features_notification: {e}")
        await callback.message.answer(f"❌ Ошибка при рассылке: {str(e)}")

@router.callback_query(F.data == "notif_benefits")
async def send_benefits_notification(callback: types.CallbackQuery, bot):
    """Отправляет напоминание о преимуществах подписки."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        user_ids = await get_all_user_ids()
        if not user_ids:
            await callback.message.answer("В базе данных нет пользователей.")
            return
        
        message_text = (
            "💎 Напоминание о преимуществах вашей подписки\n\n"
            "🔒 Что вы получаете:\n"
            "• Полная анонимность в сети\n"
            "• Обход любых блокировок\n"
            "• Доступ к иностранным ресурсам\n"
            "• Высокая скорость соединения\n"
            "• Поддержка 24/7\n\n"
            "🎯 Используйте все возможности вашей подписки!\n\n"
            "Спасибо за доверие! 💙"
        )
        
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, message_text)
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send benefits notification to {user_id}: {e}")
                failed += 1
            await asyncio.sleep(0.05)
        
        await callback.message.answer(
            f"✅ Рассылка о преимуществах завершена!\n\n"
            f"📊 Статистика:\n"
            f"• Отправлено: {sent}\n"
            f"• Ошибок: {failed}\n"
            f"• Всего пользователей: {len(user_ids)}"
        )
        
    except Exception as e:
        logger.error(f"Error in send_benefits_notification: {e}")
        await callback.message.answer(f"❌ Ошибка при рассылке: {str(e)}")

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

@router.message(AdminStates.waiting_for_promo_message)
async def process_promo_message(message: types.Message, state: FSMContext, bot):
    """Обрабатывает промо-сообщение и отправляет его всем пользователям."""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа.")
        await state.clear()
        return
    
    promo_text = message.text
    if not promo_text or len(promo_text.strip()) == 0:
        await message.answer("Сообщение не может быть пустым. Попробуйте снова:")
        return
    
    try:
        user_ids = await get_all_user_ids()
        if not user_ids:
            await message.answer("В базе данных нет пользователей.")
            await state.clear()
            return
        
        await message.answer(f"🔥 Начинаю промо-рассылку {len(user_ids)} пользователям...")
        
        sent_count = 0
        failed_count = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, promo_text)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send promo message to user {user_id}: {e}")
                failed_count += 1
            await asyncio.sleep(0.05)
        
        await message.answer(
            f"✅ Промо-рассылка завершена!\n\n"
            f"📊 Статистика:\n"
            f"• Отправлено: {sent_count}\n"
            f"• Ошибок: {failed_count}\n"
            f"• Всего пользователей: {len(user_ids)}"
        )
        
    except Exception as e:
        logger.error(f"Error during promo broadcast: {e}")
        await message.answer(f"❌ Ошибка при промо-рассылке: {str(e)}")
    
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
    """Получает список всех tg_id из bot БД."""
    try:
        import aiosqlite
        
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT tg_id FROM users")
                rows = await cursor.fetchall()
                return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"Error getting user IDs: {e}")
        return []

async def get_users_without_subscription() -> list[str]:
    """Получает список пользователей без активной подписки."""
    try:
        import aiosqlite
        
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                # Пользователи без баланса (без активной подписки)
                await cursor.execute("SELECT tg_id FROM users WHERE balance <= 0")
                rows = await cursor.fetchall()
                return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"Error getting users without subscription: {e}")
        return []

async def get_users_with_expired_subscription() -> list[str]:
    """Получает список пользователей с истекшей подпиской."""
    try:
        import aiosqlite
        
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                # Пользователи, которые когда-то имели подписку, но сейчас без баланса
                # (использовали пробную подписку или имели платную, но она истекла)
                await cursor.execute(
                    "SELECT tg_id FROM users WHERE balance <= 0 AND (trial_3d_used = 1 OR paid_count > 0)"
                )
                rows = await cursor.fetchall()
                return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"Error getting users with expired subscription: {e}")
        return []

async def get_users_with_active_subscription() -> list[str]:
    """Получает список пользователей с активной подпиской через FastAPI API."""
    try:
        # Поскольку /getids возвращает только пользователей с истекающими подписками,
        # а нам нужны все активные пользователи, используем простой подход:
        # получаем всех пользователей из bot БД и проверяем их через /usercodes
        all_bot_users = await get_all_user_ids()
        active_users = []
        
        async with aiohttp.ClientSession() as session:
            for user_id in all_bot_users:
                try:
                    url = f"{API_BASE_URL}/usercodes/{user_id}"
                    headers = {"X-API-Key": AUTH_CODE}
                    async with session.get(url, headers=headers, timeout=15) as resp:
                        if resp.status == 200:
                            # Разбираем конфиги и ищем действительно АКТИВНЫЕ (time_end > now)
                            try:
                                data = await resp.json()
                            except Exception:
                                # Ошибка парсинга — пропускаем пользователя (не рассылаем)
                                active_users.append(user_id)
                                continue
                            now_ts = int(time.time())
                            def _parse_time_end(raw: object) -> int:
                                try:
                                    val = int(raw)
                                except Exception:
                                    return 0
                                # Защита от миллисекунд
                                if val > 10**11:
                                    val = val // 1000
                                return val
                            has_active = any(_parse_time_end(item.get("time_end", 0)) > now_ts for item in data)
                            if has_active:
                                active_users.append(user_id)
                        else:
                            # 404 — нет конфигов у пользователя (точно не активный)
                            if resp.status == 404:
                                pass
                            else:
                                # Любая иная ошибка API — подстраховка: пропускаем такого пользователя
                                active_users.append(user_id)
                except Exception:
                    # Сетевая ошибка — пропускаем такого пользователя (не рассылаем)
                    active_users.append(user_id)
                    continue
        return active_users
    except Exception as e:
        logger.error(f"Error getting users with active subscription: {e}")
        return []

async def get_users_without_any_subscription() -> list[str]:
    """Получает пользователей без подписки (не в FastAPI БД)."""
    try:
        # Получаем всех пользователей из bot БД
        all_bot_users = await get_all_user_ids()
        
        # Получаем пользователей с активной подпиской из FastAPI
        active_sub_users = await get_users_with_active_subscription()
        
        # Возвращаем пользователей, которых нет в списке активных подписок
        return [user_id for user_id in all_bot_users if user_id not in active_sub_users]
    except Exception as e:
        logger.error(f"Error getting users without any subscription: {e}")
        return []


async def get_users_trial_only_no_payments() -> list[int]:
    """Пользователи, кто активировал пробную (trial_3d_used=1), но ещё ни разу не покупал (paid_count=0).

    Возвращаем список tg_id как int.
    """
    try:
        import aiosqlite
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT tg_id FROM users WHERE trial_3d_used = 1 AND (paid_count IS NULL OR paid_count = 0)"
                )
                rows = await cursor.fetchall()
                res: list[int] = []
                for row in rows:
                    try:
                        res.append(int(row[0]))
                    except Exception:
                        continue
                return res
    except Exception as e:
        logger.error(f"Error getting users trial-only: {e}")
        return []


@router.callback_query(F.data == "notif_trial_only")
async def send_trial_only_notification(callback: types.CallbackQuery, bot):
    """Рассылка пользователям, кто активировал пробную, но не совершал оплату.

    Текст включает: обход отключений интернета на Теле2/МТС/Йота + дополнительные преимущества.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.answer()

    try:
        user_ids = await get_users_trial_only_no_payments()
        if not user_ids:
            await callback.message.answer("Нет пользователей, которые только активировали пробную, но не покупали.")
            return

        message_text = (
            "👋 Привет! Напоминаем, что после пробной подписки вы ещё не оформили полный доступ.\n\n"
            "⚡ Важное сейчас: наш VPN помогает обходить отключения мобильного интернета у операторов Теле2, МТС и ЙОТА.\n"
            "Даже когда связь режут, вы сможете пользоваться интернетом.\n\n"
            "С подпиской вы получаете:\n"
            "• 🔐 Конфиденциальность и шифрование трафика\n"
            "• ♾️ Безлимитный трафик\n"
            "• 🚀 Стабильная скорость и быстрые сервера\n"
            "• 🛟 Поддержка, если что-то пойдёт не так\n\n"
            "Готовы продолжить? Откройте /start и выберите тариф. Если остались вопросы — напишите в поддержку, поможем."
        )

        sent = 0
        failed = 0
        for uid in user_ids:
            try:
                await bot.send_message(uid, message_text, disable_web_page_preview=True)
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send trial-only message to {uid}: {e}")
                failed += 1
            await asyncio.sleep(0.05)

        await callback.message.answer(
            f"✅ Рассылка по пользователям только с пробной завершена!\n\n"
            f"Отправлено: {sent}\nОшибок: {failed}\nВсего: {len(user_ids)}"
        )
    except Exception as e:
        logger.error(f"Error in send_trial_only_notification: {e}")
        await callback.message.answer(f"❌ Ошибка при рассылке: {str(e)}")


async def get_user_stats() -> dict:
    """Получает статистику пользователей из локальной БД bot контейнера."""
    try:
        import aiosqlite
        
        # Получаем статистику из локальной БД bot контейнера
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                # Общее количество пользователей в bot БД
                await cursor.execute("SELECT COUNT(*) FROM users")
                total_users = (await cursor.fetchone())[0]
                
                # Пользователи, использовавшие пробную подписку
                await cursor.execute("SELECT COUNT(*) FROM users WHERE trial_3d_used = 1")
                trial_used = (await cursor.fetchone())[0]
                
                # Пользователи с балансом дней
                await cursor.execute("SELECT COUNT(*) FROM users WHERE balance > 0")
                with_balance = (await cursor.fetchone())[0]
                
                # Общее количество рефералов
                await cursor.execute("SELECT SUM(referral_count) FROM users")
                total_referrals_result = await cursor.fetchone()
                total_referrals = total_referrals_result[0] if total_referrals_result[0] is not None else 0
        
        return {
            'total_users': total_users,
            'trial_used': trial_used,
            'with_balance': with_balance,
            'total_referrals': total_referrals
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
            f"• 🇫🇮 Финляндия: {config_stats['fi_count']}\n"
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
            f"• 🇫🇮 Финляндия: {detailed_stats['configs']['fi']}\n"
            f"• 🇳🇱 Нидерланды: {detailed_stats['configs']['nl']}\n"
            f"• 🇩🇪 Германия: {detailed_stats['configs']['ge']}\n\n"
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
        [InlineKeyboardButton(text="💵 Доход (руб / звезды)", callback_data="admin_revenue")],
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
    """Получает информацию о пользователе из локальной БД и API."""
    try:
        import aiosqlite
        
        # Получаем информацию из локальной БД bot контейнера
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT tg_id, trial_3d_used, balance, referral_count, referral_code
                    FROM users WHERE tg_id = ?
                """, (str(tg_id),))
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                tg_id_db, trial_used, balance, referral_count, referral_code = row
        
        # Получаем информацию о конфигах из API
        active_configs = 0
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                headers = {"X-API-Key": AUTH_CODE}
                async with session.get(f"{API_BASE_URL}/usercodes/{tg_id}", headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            configs = await resp.json()
                            active_configs = len([c for c in configs if c.get('time_end', 0) > int(time.time())])
                        except aiohttp.ContentTypeError as e:
                            logger.error(f"Invalid JSON response: {e}")
        except Exception as e:
            logger.warning(f"Could not get config info from API: {e}")
        
        return {
            'tg_id': str(tg_id),
            'trial_used': bool(trial_used),
            'balance': balance or 0,
            'referral_count': referral_count or 0,
            'referral_code': referral_code or 'Не создан',
            'created_at': 'Неизвестно',  # В БД нет поля created_at
            'active_configs': active_configs
        }
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
                        'fi_count': 0, 'nl_count': 0, 'ge_count': 0
                    }
                
                try:
                    data = await resp.json()
                except aiohttp.ContentTypeError as e:
                    logger.error(f"Invalid JSON response: {e}")
                    return {
                        'total': 0, 'active': 0, 'expired': 0, 'free': 0,
                        'fi_count': 0, 'nl_count': 0, 'ge_count': 0
                    }
                
                configs = data.get('configs', [])
                
                current_time = int(time.time())
                total = len(configs)
                active = len([c for c in configs if c.get('time_end', 0) > current_time])
                expired = len([c for c in configs if c.get('time_end', 0) <= current_time and c.get('time_end', 0) > 0])
                free = len([c for c in configs if c.get('time_end', 0) == 0])
                fi_count = len([c for c in configs if c.get('server_country') == 'fi'])
                nl_count = len([c for c in configs if c.get('server_country') == 'nl'])
                ge_count = len([c for c in configs if c.get('server_country') == 'ge'])
                
                return {
                    'total': total,
                    'active': active,
                    'expired': expired,
                    'free': free,
                    'fi_count': fi_count,
                    'nl_count': nl_count,
                    'ge_count': ge_count
                }
    except aiohttp.ClientError as e:
        logger.error(f"Network error getting config statistics: {e}")
        return {
            'total': 0, 'active': 0, 'expired': 0, 'free': 0,
            'fi_count': 0, 'nl_count': 0, 'ge_count': 0
        }
    except Exception as e:
        logger.error(f"Error getting config statistics: {e}")
        return {
            'total': 0, 'active': 0, 'expired': 0, 'free': 0,
            'fi_count': 0, 'nl_count': 0, 'ge_count': 0
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
                    time_end_formatted = datetime.fromtimestamp(time_end).strftime("%d.%m.%Y %H:%M")
                
                return {
                    'uid': config.get('uid'),
                    'tg_id': config.get('tg_id') or 'Не назначен',
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
    """Получает детальную статистику из bot БД и API."""
    try:
        import aiosqlite
        
        # Получаем статистику пользователей из bot БД
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                # Общее количество пользователей
                await cursor.execute("SELECT COUNT(*) FROM users")
                total_users = (await cursor.fetchone())[0]
                
                # Пользователи, использовавшие пробную подписку
                await cursor.execute("SELECT COUNT(*) FROM users WHERE trial_3d_used = 1")
                trial_used = (await cursor.fetchone())[0]
                
                # Пользователи с балансом дней
                await cursor.execute("SELECT COUNT(*) FROM users WHERE balance > 0")
                with_balance = (await cursor.fetchone())[0]
                
                # Общее количество рефералов
                await cursor.execute("SELECT SUM(referral_count) FROM users")
                total_referrals_result = await cursor.fetchone()
                total_referrals = total_referrals_result[0] if total_referrals_result[0] is not None else 0
                
                # Топ реферер
                await cursor.execute("""
                    SELECT tg_id, referral_count 
                    FROM users 
                    WHERE referral_count > 0 
                    ORDER BY referral_count DESC 
                    LIMIT 1
                """)
                top_referrer_row = await cursor.fetchone()
                top_referrer = f"ID: {top_referrer_row[0]} ({top_referrer_row[1]} рефералов)" if top_referrer_row else "Нет данных"
        
        # Получаем статистику конфигов из API
        config_stats = await get_config_statistics()
        
        return {
            'users': {
                'total': total_users,
                'active': config_stats['active'],  # Активные пользователи = пользователи с активными конфигами
                'trial_used': trial_used,
                'with_balance': with_balance
            },
            'configs': {
                'total': config_stats['total'],
                'active': config_stats['active'],
                'expired': config_stats['expired'],
                'fi': config_stats['fi_count'],
                'nl': config_stats['nl_count'],
                'ge': config_stats['ge_count']
            },
            'referrals': {
                'total': total_referrals,
                'top_referrer': top_referrer
            }
        }
    except Exception as e:
        logger.error(f"Error getting detailed statistics: {e}")
        return {
            'users': {'total': 0, 'active': 0, 'trial_used': 0, 'with_balance': 0},
            'configs': {'total': 0, 'active': 0, 'expired': 0, 'fi': 0, 'nl': 0, 'ge': 0},
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
            f"• 🇳🇱 Нидерланды: {config_stats['nl_count']}\n"
            f"• 🇩🇪 Германия: {config_stats['ge_count']}\n\n"
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
