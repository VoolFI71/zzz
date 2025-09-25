from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
import aiosqlite
import logging

logger = logging.getLogger(__name__)

router = Router()

# ID администратора
ADMIN_ID = 746560409

class AdminStates(StatesGroup):
    waiting_for_message = State()

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_ID

@router.message(F.text == "🔧 Админ панель")
async def admin_panel(message: types.Message):
    """Показывает админ панель только для администратора."""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ панели.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
    ])
    
    await message.answer(
        "🔧 Админ панель\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс отправки сообщения всем пользователям."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 Отправка сообщения всем пользователям\n\n"
        "Введите сообщение, которое хотите отправить всем пользователям:"
    )
    await state.set_state(AdminStates.waiting_for_message)
    await callback.answer()

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
    """Получает список всех tg_id из базы данных."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT DISTINCT tg_id FROM users WHERE tg_id IS NOT NULL AND tg_id != ''")
            rows = await cursor.fetchall()
            return [row[0] for row in rows if row[0]]

async def get_user_stats() -> dict:
    """Получает статистику пользователей."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            # Общее количество пользователей
            await cursor.execute("SELECT COUNT(DISTINCT tg_id) FROM users WHERE tg_id IS NOT NULL AND tg_id != ''")
            total_users = (await cursor.fetchone())[0]
            
            # Количество использовавших пробную подписку
            await cursor.execute("SELECT COUNT(*) FROM users WHERE trial_3d_used = 1")
            trial_used = (await cursor.fetchone())[0]
            
            # Количество пользователей с балансом
            await cursor.execute("SELECT COUNT(*) FROM users WHERE balance > 0")
            with_balance = (await cursor.fetchone())[0]
            
            # Общее количество рефералов
            await cursor.execute("SELECT SUM(referral_count) FROM users WHERE referral_count > 0")
            total_referrals_row = await cursor.fetchone()
            total_referrals = total_referrals_row[0] if total_referrals_row[0] else 0
            
            return {
                'total_users': total_users,
                'trial_used': trial_used,
                'with_balance': with_balance,
                'total_referrals': total_referrals
            }
