from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import time
import aiohttp
import asyncio
import os

logger = logging.getLogger(__name__)

router = Router()

# API настройки
API_BASE_URL = "http://fastapi:8080"
AUTH_CODE = os.getenv("AUTH_CODE")

# Импортируем is_admin из main модуля
from .main import is_admin

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
        [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_panel")],
    ])
    
    await callback.message.edit_text(
        "🔔 Уведомления для увеличения продаж\n\n"
        "Выберите тип рассылки:",
        reply_markup=keyboard
    )
    await callback.answer()

# Импортируем функции из других модулей
from .statistics import (
    get_users_without_any_subscription,
    get_users_with_expired_subscription,
    get_users_trial_only_no_payments
)

@router.callback_query(F.data == "notif_no_sub")
async def send_no_sub_notification(callback: types.CallbackQuery, bot):
    """Рассылка пользователям без подписки для привлечения."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.answer()

    try:
        # Получаем пользователей без подписки
        user_ids = await get_users_without_any_subscription()
        if not user_ids:
            await callback.message.answer("Нет пользователей без подписки.")
            return

        message_text = (
            "👋 Привет! Мы заметили, что вы ещё не попробовали наш VPN.\n\n"
            "⚡ Сейчас это особенно актуально: наш VPN помогает обходить отключения мобильного интернета у операторов Теле2, МТС и ЙОТА.\n"
            "Даже когда связь режут, вы сможете пользоваться интернетом.\n\n"
            "🎁 Попробуйте бесплатно 3 дня — никаких ограничений!\n\n"
            "С подпиской вы получаете:\n"
            "• 🔐 Конфиденциальность и шифрование трафика\n"
            "• ♾️ Безлимитный трафик\n"
            "• 🚀 Стабильная скорость и быстрые сервера\n"
            "• 🛟 Поддержка, если что-то пойдёт не так\n\n"
            "Готовы попробовать? Откройте /start и активируйте пробную подписку. Если остались вопросы — напишите в поддержку, поможем."
        )

        sent = 0
        failed = 0
        for uid in user_ids:
            try:
                await bot.send_message(uid, message_text, disable_web_page_preview=True)
                sent += 1
                await asyncio.sleep(0.1)  # Пауза между отправками
            except Exception as e:
                logger.warning(f"Failed to send to {uid}: {e}")
                failed += 1

        await callback.message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"Отправлено: {sent}\n"
            f"Не доставлено: {failed}\n"
            f"Всего пользователей: {len(user_ids)}"
        )

    except Exception as e:
        logger.error(f"Error in send_no_sub_notification: {e}")
        await callback.message.answer(f"Ошибка при рассылке: {e}")

@router.callback_query(F.data == "notif_expired")
async def send_expired_notification(callback: types.CallbackQuery, bot):
    """Рассылка пользователям с истекшей подпиской для возврата."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.answer()

    try:
        # Получаем пользователей с истекшей подпиской
        user_ids = await get_users_with_expired_subscription()
        if not user_ids:
            await callback.message.answer("Нет пользователей с истекшей подпиской.")
            return

        message_text = (
            "👋 Привет! Мы заметили, что ваша подписка истекла.\n\n"
            "⚡ Сейчас наш VPN особенно актуален: помогает обходить отключения мобильного интернета у операторов Теле2, МТС и ЙОТА.\n"
            "Даже когда связь режут, вы сможете пользоваться интернетом.\n\n"
            "🔥 Специальное предложение для возврата:\n"
            "• 🎁 Скидка 20% на первый месяц\n"
            "• 🚀 Улучшенная скорость и стабильность\n"
            "• 🛟 Приоритетная поддержка\n\n"
            "Готовы вернуться? Откройте /start и выберите тариф. Если остались вопросы — напишите в поддержку, поможем."
        )

        sent = 0
        failed = 0
        for uid in user_ids:
            try:
                await bot.send_message(uid, message_text, disable_web_page_preview=True)
                sent += 1
                await asyncio.sleep(0.1)  # Пауза между отправками
            except Exception as e:
                logger.warning(f"Failed to send to {uid}: {e}")
                failed += 1

        await callback.message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"Отправлено: {sent}\n"
            f"Не доставлено: {failed}\n"
            f"Всего пользователей: {len(user_ids)}"
        )

    except Exception as e:
        logger.error(f"Error in send_expired_notification: {e}")
        await callback.message.answer(f"Ошибка при рассылке: {e}")

@router.callback_query(F.data == "notif_promo")
async def send_promo_notification(callback: types.CallbackQuery, state: FSMContext):
    """Рассылка промо-сообщения."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.answer()
    await state.set_state("waiting_for_promo_message")
    await callback.message.edit_text(
        "📝 Введите текст промо-сообщения для рассылки:"
    )

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

        # Дополнительная проверка: исключаем пользователей с активными подписками
        from .statistics import get_users_with_active_subscription
        active_users = await get_users_with_active_subscription()
        active_user_ids = set(active_users)
        
        # Фильтруем список, исключая пользователей с активными подписками
        filtered_user_ids = [uid for uid in user_ids if str(uid) not in active_user_ids]
        
        if not filtered_user_ids:
            await callback.message.answer("Нет пользователей для рассылки (все имеют активные подписки).")
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
        for uid in filtered_user_ids:
            try:
                await bot.send_message(uid, message_text, disable_web_page_preview=True)
                sent += 1
                await asyncio.sleep(0.1)  # Пауза между отправками
            except Exception as e:
                logger.warning(f"Failed to send to {uid}: {e}")
                failed += 1

        await callback.message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"Отправлено: {sent}\n"
            f"Не доставлено: {failed}\n"
            f"Всего пользователей: {len(filtered_user_ids)}"
        )

    except Exception as e:
        logger.error(f"Error in send_trial_only_notification: {e}")
        await callback.message.answer(f"Ошибка при рассылке: {e}")
