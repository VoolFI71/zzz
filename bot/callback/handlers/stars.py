"""Оплата через Telegram Stars."""

from __future__ import annotations

import asyncio
import os
import time
import logging
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from utils import check_available_configs

logger = logging.getLogger(__name__)

stars_router = Router()


@stars_router.callback_query(F.data == "pay_star")
async def pay_with_stars(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    tg_id = callback_query.from_user.id

    user_data = await state.get_data()
    # Подписка на 1 или 3 месяца
    days = int(user_data.get("selected_days", 31))
    # Маппинг payload по длительности (31 → 1м, всё остальное → 3м)
    payload = "sub_1m" if days == 31 else "sub_3m"

    # Анти-спам и один активный счёт на пользователя
    now_ts = int(time.time())
    last_click_ts = user_data.get("last_buy_click_ts")
    if last_click_ts and (now_ts - int(last_click_ts) < 3):
        await callback_query.answer("Подождите пару секунд…", show_alert=False)
        return
    await state.update_data(last_buy_click_ts=now_ts)

    existing_invoice_id = user_data.get("invoice_msg_id")
    if existing_invoice_id:
        await callback_query.answer("У вас уже есть неоплаченный счёт выше ⬆️", show_alert=True)
        return

    # Проверяем, есть ли у пользователя уже активные конфиги
    existing_configs = await db.get_codes_by_tg_id(tg_id)
    
    if existing_configs:
        # У пользователя есть конфиги - предлагаем продление
        await callback_query.message.edit_text(
            "У вас уже есть активная подписка! Вы хотите продлить её?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Продлить подписку", callback_data="extend_subscription")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
            ])
        )
        await callback_query.answer()
        return
    
    # У пользователя нет конфигов - создаем новые на всех серверах
    # Используем все серверы из SERVER_ORDER (как при покупке подписки)
    env_order = os.getenv("SERVER_ORDER", "fi")
    servers_to_use = [s.strip().lower() for s in env_order.split(',') if s.strip()]
    
    # Сохраняем список серверов для использования
    await state.update_data(servers_to_use=servers_to_use)

    provider_token = ""

    try:
        await bot.delete_message(chat_id=tg_id, message_id=callback_query.message.message_id)
    except Exception:
        pass

    # Создаём счёт
    if payload == "sub_1m":
        invoice_msg = await bot.send_invoice(
            chat_id=tg_id,
            title="Подписка на 1 месяц",
            description="Доступ к GLS VPN на 1 месяц",
            payload=payload,
            provider_token=provider_token,
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=int(os.getenv("PRICE_1M_STAR", "149")))],
            max_tip_amount=0,
        )
    else:
        invoice_msg = await bot.send_invoice(
            chat_id=tg_id,
            title="Подписка на 3 месяца",
            description="GLS VPN доступ на 3 месяца",
            payload=payload,
            provider_token=provider_token,
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=int(os.getenv("PRICE_3M_STAR", "349")))],
            max_tip_amount=0,
        )

    try:
        await state.update_data(invoice_msg_id=invoice_msg.message_id, invoice_created_ts=now_ts)
    except Exception:
        pass

    # Авто-истечение (4 минуты)
    async def _expire_invoice() -> None:
        try:
            await asyncio.sleep(4 * 60)
            data_state = await state.get_data()
            current_invoice_id = data_state.get("invoice_msg_id")
            if current_invoice_id == invoice_msg.message_id:
                try:
                    await bot.delete_message(chat_id=tg_id, message_id=invoice_msg.message_id)
                except Exception:
                    pass
                try:
                    await state.update_data(invoice_msg_id=None)
                except Exception:
                    pass
                try:
                    await bot.send_message(tg_id, "Счёт истёк. Если хотите, создайте новый.")
                except Exception:
                    pass
        except Exception:
            pass

    asyncio.create_task(_expire_invoice())
    await callback_query.answer("Создаём счёт для оплаты...")

    # Отдельное сервисное сообщение управления счётом
    try:
        control_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить счёт", callback_data="cancel_star_invoice")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
        control_msg = await bot.send_message(
            chat_id=tg_id,
            text="Для управления счётом используйте кнопки ниже:",
            reply_markup=control_kb,
        )
        try:
            await state.update_data(invoice_ctrl_msg_id=control_msg.message_id)
        except Exception:
            pass
    except Exception:
        pass


@stars_router.pre_checkout_query(lambda _: True)
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot) -> None:
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@stars_router.message(F.successful_payment)
async def successful_payment_handler(message: Message, bot: Bot, state: FSMContext) -> None:
    from utils import get_session
    tg_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    payload_to_days = {"sub_1m": 31, "sub_3m": 93}
    days = payload_to_days.get(payload, 31)
    user_data = await state.get_data()
    
    # Проверяем, есть ли у пользователя уже конфиги
    existing_configs = await db.get_codes_by_tg_id(tg_id)
    
    if existing_configs:
        # Продлеваем существующие конфиги
        await extend_existing_configs(tg_id, days, bot)
    else:
        # Выдаем конфиги на всех серверах
        servers_to_use = user_data.get("servers_to_use", ["fi"])
        await give_configs_on_all_servers(tg_id, days, servers_to_use, bot)
    
    # Записываем платеж в статистику
    amount = message.successful_payment.total_amount
    await db.mark_payment(tg_id, days)
    await db.add_star_payment(amount)
    
    # Начисляем бонус рефералу
    inviter_tg_id = await db.get_referrer_id(str(tg_id))
    if inviter_tg_id:
        try:
            # Начисляем бонусные дни (например, 2 дня)
            BONUS_DAYS = int(days//10)
            await db.add_balance_days(str(inviter_tg_id), BONUS_DAYS)
            try:
                await bot.send_message(int(inviter_tg_id),
                                    f"Ваш реферал оплатил подписку — вам начислено {BONUS_DAYS} дня(ей) бонуса. Вы можете активировать их в личном кабинете. При активации дни не суммируются с текущим конфигом в подписке.")
            except Exception:
                pass
        except Exception as exc:
            logger.error("Ошибка начисления бонуса пригласителю %s: %s", inviter_tg_id, exc)
    
    # Уведомляем админа
    try:
        admin_id = 746560409
        if admin_id:
            at_username = (f"@{message.from_user.username}" if getattr(message.from_user, "username", None) else "—")
            await bot.send_message(admin_id, f"Оплачена подписка через Stars: user_id={tg_id}, user={at_username}, срок={days} дн.")
    except Exception:
        pass

    # Очистка инвойса
    try:
        data_state = await state.get_data()
        invoice_msg_id = data_state.get("invoice_msg_id")
        if invoice_msg_id:
            await bot.delete_message(chat_id=tg_id, message_id=invoice_msg_id)
            await state.update_data(invoice_msg_id=None)
        ctrl_msg_id = data_state.get("invoice_ctrl_msg_id")
        if ctrl_msg_id:
            try:
                await bot.delete_message(chat_id=tg_id, message_id=ctrl_msg_id)
            except Exception:
                pass
            try:
                await state.update_data(invoice_ctrl_msg_id=None)
            except Exception:
                pass
    except Exception:
        pass

    # Дополнительной пометки по тестовым тарифам не требуется


@stars_router.callback_query(F.data == "extend_subscription")
async def extend_subscription_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик продления подписки."""
    tg_id = callback_query.from_user.id
    user_data = await state.get_data()
    days = int(user_data.get("selected_days", 31))
    
    # Создаем инвойс для продления
    payload = "sub_1m" if days == 31 else "sub_3m"
    star_1m = int(os.getenv("PRICE_1M_STAR", "149"))
    star_3m = int(os.getenv("PRICE_3M_STAR", "349"))
    amount = star_1m if days == 31 else star_3m
    
    try:
        await bot.send_invoice(
            chat_id=tg_id,
            title=f"Продление подписки GLS VPN — {days} дн.",
            description=f"Продление подписки на {days} дней",
            payload=payload,
            provider_token="",
            currency="XTR",  # Telegram Stars
            prices=[LabeledPrice(label=f"{days} дн.", amount=amount)],
        )
        await callback_query.answer("Счёт для продления создан!")
    except Exception as e:
        logger.error(f"Failed to create extend invoice: {e}")
        await callback_query.answer("Ошибка создания счёта", show_alert=True)


@stars_router.callback_query(F.data == "cancel_payment")
async def cancel_payment_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик отмены оплаты."""
    await callback_query.message.edit_text("Оплата отменена.")
    await callback_query.answer()


@stars_router.callback_query(F.data == "cancel_star_invoice")
async def cancel_star_invoice(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    tg_id = callback_query.from_user.id
    try:
        data_state = await state.get_data()
        invoice_msg_id = data_state.get("invoice_msg_id")
        if invoice_msg_id:
            try:
                await bot.delete_message(chat_id=tg_id, message_id=invoice_msg_id)
            except Exception:
                pass
            await state.update_data(invoice_msg_id=None)
        ctrl_msg_id = data_state.get("invoice_ctrl_msg_id")
        if ctrl_msg_id:
            try:
                await bot.delete_message(chat_id=tg_id, message_id=ctrl_msg_id)
            except Exception:
                pass
            await state.update_data(invoice_ctrl_msg_id=None)
    except Exception:
        pass
    # Возвращаемся к выбору способа оплаты
    try:
        days = int((await state.get_data()).get("selected_days", 31))
        star_1m = int(os.getenv("PRICE_1M_STAR", "149"))
        star_3m = int(os.getenv("PRICE_3M_STAR", "349"))
        rub_1m = int(os.getenv("PRICE_1M_RUB", "149"))
        rub_3m = int(os.getenv("PRICE_3M_RUB", "349"))

        if days == 31:
            star_amount, rub_amount = star_1m, rub_1m
        else:
            star_amount, rub_amount = star_3m, rub_3m
        from keyboards.keyboard import create_payment_method_keyboard
        await bot.send_message(
            tg_id,
            f"Выбран тариф: {days} дн. Выберите способ оплаты:",
            reply_markup=create_payment_method_keyboard(star_amount, rub_amount),
        )
    except Exception:
        pass
    await callback_query.answer("Счёт отменён")


async def give_configs_on_all_servers(tg_id: int, days: int, servers: list, bot: Bot) -> None:
    """Выдает конфиги на всех указанных серверах для нового пользователя."""
    from utils import get_session
    import aiohttp
    
    AUTH_CODE = os.getenv("AUTH_CODE")
    urlupdate = "http://fastapi:8080/giveconfig"
    session = await get_session()
    
    success_count = 0
    failed_servers = []
    
    for server in servers:
        try:
            data = {"time": days, "id": str(tg_id), "server": server}
            async with session.post(urlupdate, json=data, headers={"X-API-Key": AUTH_CODE}) as resp:
                if resp.status == 200:
                    success_count += 1
                else:
                    failed_servers.append(server)
        except Exception as e:
            logger.error(f"Failed to create config on server {server}: {e}")
            failed_servers.append(server)
    
    # Уведомляем пользователя о результате
    if success_count > 0:
        try:
            sub_key = await db.get_or_create_sub_key(str(tg_id))
            base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
            sub_url = f"{base}/subscription/{sub_key}"
            await bot.send_message(tg_id, f"✅ Подписка активирована!\n\nВаша ссылка подписки: {sub_url}")
        except Exception:
            await bot.send_message(tg_id, f"✅ Подписка активирована!")
    
    if failed_servers:
        await bot.send_message(tg_id, f"⚠️ Не удалось создать конфиги на серверах: {', '.join(failed_servers)}")


async def extend_existing_configs(tg_id: int, days: int, bot: Bot) -> None:
    """Продлевает существующие конфиги пользователя."""
    from utils import get_session
    import aiohttp
    
    AUTH_CODE = os.getenv("AUTH_CODE")
    urlextend = "http://fastapi:8080/extendconfig"
    session = await get_session()
    
    # Получаем все конфиги пользователя
    existing_configs = await db.get_codes_by_tg_id(tg_id)
    success_count = 0
    failed_configs = []
    
    for user_code, time_end, server in existing_configs:
        try:
            data = {"time": days, "uid": user_code, "server": server}
            async with session.post(urlextend, json=data, headers={"X-API-Key": AUTH_CODE}) as resp:
                if resp.status == 200:
                    success_count += 1
                else:
                    failed_configs.append(user_code)
        except Exception as e:
            logger.error(f"Failed to extend config {user_code}: {e}")
            failed_configs.append(user_code)
    
    # Уведомляем пользователя о результате
    if success_count > 0:
        await bot.send_message(tg_id, f"✅ Подписка продлена на {success_count} конфигах!")
    
    if failed_configs:
        await bot.send_message(tg_id, f"⚠️ Не удалось продлить {len(failed_configs)} конфигов")


