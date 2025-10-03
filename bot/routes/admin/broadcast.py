from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import aiosqlite

logger = logging.getLogger(__name__)

router = Router()

class AdminStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_promo_message = State()

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == 746560409

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

async def get_all_user_ids() -> list[str]:
    """Получает список всех tg_id из bot БД."""
    try:
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT tg_id FROM users")
                rows = await cursor.fetchall()
                return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"Error getting user IDs: {e}")
        return []
