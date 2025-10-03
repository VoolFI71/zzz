from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)

router = Router()

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == 746560409

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
