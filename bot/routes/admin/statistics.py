from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import time
import aiohttp
import aiosqlite
import os

logger = logging.getLogger(__name__)

router = Router()

# API настройки
API_BASE_URL = "http://fastapi:8080"
AUTH_CODE = os.getenv("AUTH_CODE")

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == 746560409

@router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: types.CallbackQuery):
    """Показывает детальную статистику пользователей."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        # Получаем все виды статистики
        user_stats = await get_user_stats()
        payment_stats = await get_payment_stats()
        subscription_stats = await get_subscription_stats()
        activity_stats = await get_activity_stats()
        
        # Формируем детальную статистику
        stats_text = (
            f"📊 **Детальная статистика**\n\n"
            f"👥 **Пользователи:**\n"
            f"• Всего: {user_stats['total_users']}\n"
            f"• С платежами: {user_stats['paid_users']}\n"
            f"• Только пробная: {user_stats['trial_only_users']}\n"
            f"• С балансом: {user_stats['with_balance']}\n\n"
            f"📈 **Активность:**\n"
            f"• Пробные подписки: {user_stats['new_users_week']}\n"
            f"• Платежи за 24ч: {activity_stats['active_24h']}\n"
            f"• Платежи за 7д: {activity_stats['active_7d']}\n"
            f"• Платежи за 30д: {activity_stats['active_30d']}\n"
            f"• Конверсия пробная→платная: {activity_stats['conversion_rate']:.1f}%\n\n"
            f"🔔 **Подписки:**\n"
            f"• Активные: {subscription_stats['active_subscriptions']}\n"
            f"• Без подписки: {subscription_stats['no_subscriptions']}\n"
            f"• Истекшие: {subscription_stats['expired_subscriptions']}\n"
            f"• Только пробные: {subscription_stats['trial_only_users']}\n\n"
            f"🤝 **Реферальная программа:**\n"
            f"• Всего рефералов: {user_stats['total_referrals']}\n"
            f"• Пользователей с рефералами: {user_stats['users_with_referrals']}\n"
        )
        
        # Добавляем топ реферера, если есть
        if user_stats['top_referrer']:
            tg_id, count = user_stats['top_referrer']
            stats_text += f"• Топ реферер: {tg_id} ({count} приглашений)\n\n"
        else:
            stats_text += "\n"
            
        # Добавляем статистику платежей
        stats_text += (
            f"💳 **Платежи:**\n"
            f"• Рубли: {payment_stats['total_rub']:,} ₽ ({payment_stats['count_rub']} транзакций)\n"
            f"• Звезды: {payment_stats['total_stars']:,} ⭐ ({payment_stats['count_stars']} транзакций)\n"
            f"• Средний чек (рубли): {payment_stats['avg_rub']:.0f} ₽\n"
            f"• Средний чек (звезды): {payment_stats['avg_stars']:.0f} ⭐"
        )
        
        await callback.message.edit_text(stats_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await callback.message.edit_text(f"❌ Ошибка при получении статистики: {str(e)}")
    
    await callback.answer()

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

async def get_users_without_subscription() -> list[str]:
    """Получает список пользователей без активной подписки."""
    try:
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

async def get_user_stats() -> dict:
    """Получает детальную статистику пользователей из bot БД."""
    try:
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
                await cursor.execute("SELECT SUM(referral_count) FROM users WHERE referral_count IS NOT NULL")
                total_referrals = (await cursor.fetchone())[0] or 0
                
                # Пользователи с платежами
                await cursor.execute("SELECT COUNT(*) FROM users WHERE paid_count > 0")
                paid_users = (await cursor.fetchone())[0]
                
                # Пользователи только с пробной подпиской (без платежей)
                await cursor.execute("SELECT COUNT(*) FROM users WHERE trial_3d_used = 1 AND (paid_count IS NULL OR paid_count = 0)")
                trial_only_users = (await cursor.fetchone())[0]
                
                # Пользователи с рефералами
                await cursor.execute("SELECT COUNT(*) FROM users WHERE referral_count > 0")
                users_with_referrals = (await cursor.fetchone())[0]
                
                # Топ реферер
                await cursor.execute("SELECT tg_id, referral_count FROM users WHERE referral_count > 0 ORDER BY referral_count DESC LIMIT 1")
                top_referrer = await cursor.fetchone()
                
                # Пробные подписки (приблизительный индикатор новых пользователей)
                # Поскольку у нас нет поля регистрации, используем trial_3d_used как индикатор
                await cursor.execute("SELECT COUNT(*) FROM users WHERE trial_3d_used = 1")
                trial_users_count = (await cursor.fetchone())[0]
                
                # Используем одно значение для обеих метрик, так как у нас нет временных данных
                new_users_week = trial_users_count
                new_users_month = trial_users_count
                
                return {
                    'total_users': total_users,
                    'trial_used': trial_used,
                    'with_balance': with_balance,
                    'total_referrals': total_referrals,
                    'paid_users': paid_users,
                    'trial_only_users': trial_only_users,
                    'users_with_referrals': users_with_referrals,
                    'top_referrer': top_referrer,
                    'new_users_week': new_users_week,
                    'new_users_month': new_users_month
                }
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {
            'total_users': 0,
            'trial_used': 0,
            'with_balance': 0,
            'total_referrals': 0,
            'paid_users': 0,
            'trial_only_users': 0,
            'users_with_referrals': 0,
            'top_referrer': None,
            'new_users_week': 0,
            'new_users_month': 0
        }

async def get_payment_stats() -> dict:
    """Получает статистику платежей из bot БД."""
    try:
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                # Агрегаты платежей
                await cursor.execute("SELECT total_rub, total_stars, count_rub, count_stars FROM payments_agg WHERE id = 1")
                payment_agg = await cursor.fetchone()
                
                if payment_agg:
                    total_rub, total_stars, count_rub, count_stars = payment_agg
                else:
                    total_rub = total_stars = count_rub = count_stars = 0
                
                # Средний чек в рублях
                avg_rub = total_rub / count_rub if count_rub > 0 else 0
                
                # Средний чек в звездах
                avg_stars = total_stars / count_stars if count_stars > 0 else 0
                
                return {
                    'total_rub': total_rub,
                    'total_stars': total_stars,
                    'count_rub': count_rub,
                    'count_stars': count_stars,
                    'avg_rub': avg_rub,
                    'avg_stars': avg_stars
                }
    except Exception as e:
        logger.error(f"Error getting payment stats: {e}")
        return {
            'total_rub': 0,
            'total_stars': 0,
            'count_rub': 0,
            'count_stars': 0,
            'avg_rub': 0,
            'avg_stars': 0
        }

async def get_subscription_stats() -> dict:
    """Получает статистику подписок через API."""
    try:
        # Получаем пользователей с активными подписками
        active_users = await get_users_with_active_subscription()
        
        # Получаем пользователей без подписок
        no_sub_users = await get_users_without_any_subscription()
        
        # Получаем пользователей с истекшими подписками
        expired_users = await get_users_with_expired_subscription()
        
        # Получаем пользователей только с пробной подпиской
        trial_only_users = await get_users_trial_only_no_payments()
        
        return {
            'active_subscriptions': len(active_users),
            'no_subscriptions': len(no_sub_users),
            'expired_subscriptions': len(expired_users),
            'trial_only_users': len(trial_only_users)
        }
    except Exception as e:
        logger.error(f"Error getting subscription stats: {e}")
        return {
            'active_subscriptions': 0,
            'no_subscriptions': 0,
            'expired_subscriptions': 0,
            'trial_only_users': 0
        }

async def get_activity_stats() -> dict:
    """Получает статистику активности пользователей."""
    try:
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                # Пользователи с платежами за последние 24 часа
                day_ago = int(time.time()) - (24 * 60 * 60)
                await cursor.execute("SELECT COUNT(*) FROM users WHERE last_payment_at > ?", (day_ago,))
                active_24h = (await cursor.fetchone())[0]
                
                # Пользователи с платежами за последние 7 дней
                week_ago = int(time.time()) - (7 * 24 * 60 * 60)
                await cursor.execute("SELECT COUNT(*) FROM users WHERE last_payment_at > ?", (week_ago,))
                active_7d = (await cursor.fetchone())[0]
                
                # Пользователи с платежами за последние 30 дней
                month_ago = int(time.time()) - (30 * 24 * 60 * 60)
                await cursor.execute("SELECT COUNT(*) FROM users WHERE last_payment_at > ?", (month_ago,))
                active_30d = (await cursor.fetchone())[0]
                
                # Конверсия из пробной в платную
                await cursor.execute("SELECT COUNT(*) FROM users WHERE trial_3d_used = 1 AND paid_count > 0")
                converted_users = (await cursor.fetchone())[0]
                
                await cursor.execute("SELECT COUNT(*) FROM users WHERE trial_3d_used = 1")
                total_trial_users = (await cursor.fetchone())[0]
                
                conversion_rate = (converted_users / total_trial_users * 100) if total_trial_users > 0 else 0
                
                return {
                    'active_24h': active_24h,
                    'active_7d': active_7d,
                    'active_30d': active_30d,
                    'converted_users': converted_users,
                    'conversion_rate': conversion_rate
                }
    except Exception as e:
        logger.error(f"Error getting activity stats: {e}")
        return {
            'active_24h': 0,
            'active_7d': 0,
            'active_30d': 0,
            'converted_users': 0,
            'conversion_rate': 0
        }
