"""Оплата через Telegram Stars."""

from __future__ import annotations

import asyncio
import os
import time
import logging
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from utils import check_available_configs

logger = logging.getLogger(__name__)

stars_router = Router()


@stars_router.callback_query(F.data == "pay_star")
async def pay_with_stars(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    tg_id = callback_query.from_user.id

    user_data = await state.get_data()
    days = int(user_data.get("selected_days", 31))
    payload = "sub_3d" if days == 3 else ("sub_1m" if days == 31 else "sub_3m")

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

    # Проверяем свободные конфиги
    server = user_data.get("server")
    if not await check_available_configs(server):
        await bot.send_message(tg_id, "Свободных конфигов для данного сервера нет. Попробуйте выбрать другой сервер.")
        return

    provider_token = ""

    try:
        await bot.delete_message(chat_id=tg_id, message_id=callback_query.message.message_id)
    except Exception:
        pass

    # Создаём счёт
    if payload == "sub_3d":
        invoice_msg = await bot.send_invoice(
            chat_id=tg_id,
            title="Тестовая подписка — 3 дня",
            description="GLS VPN доступ на 3 дня",
            payload=payload,
            provider_token=provider_token,
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=int(os.getenv("PRICE_3D_STAR", "5")))],
            max_tip_amount=0,
        )
    elif payload == "sub_1m":
        invoice_msg = await bot.send_invoice(
            chat_id=tg_id,
            title="Подписка на 1 месяц",
            description="Доступ к GLS VPN на 1 месяц",
            payload=payload,
            provider_token=provider_token,
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=int(os.getenv("PRICE_1M_STAR", "99")))],
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
            prices=[LabeledPrice(label="XTR", amount=int(os.getenv("PRICE_3M_STAR", "229")))],
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


@stars_router.pre_checkout_query(lambda _: True)
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot) -> None:
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@stars_router.message(F.successful_payment)
async def successful_payment_handler(message: Message, bot: Bot, state: FSMContext) -> None:
    from utils import get_session
    tg_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    days = 3 if payload == "sub_3d" else (31 if payload == "sub_1m" else 93)
    user_data = await state.get_data()
    server = user_data.get("server") or "fi"

    data = {"time": days, "id": str(tg_id), "server": server}
    AUTH_CODE = os.getenv("AUTH_CODE")
    urlupdate = "http://fastapi:8080/giveconfig"

    session = await get_session()
    try:
        async with session.post(urlupdate, json=data, headers={"X-API-Key": AUTH_CODE}) as resp:
            if resp.status == 200:
                await bot.send_message(tg_id, "Подписка активирована! Конфиг доступен в личном кабинете.")
            elif resp.status == 409:
                await bot.send_message(tg_id, "Свободных конфигов нет. Свяжитесь с поддержкой.")
            else:
                await bot.send_message(tg_id, f"Ошибка сервера ({resp.status}). Попробуйте позже.")
    except Exception as exc:
        logger.error("Ошибка обращения к FastAPI: %s", exc)
        await bot.send_message(tg_id, "Ошибка сети. Попробуйте позже или напишите в поддержку.")

    # Очистка инвойса
    try:
        data_state = await state.get_data()
        invoice_msg_id = data_state.get("invoice_msg_id")
        if invoice_msg_id:
            await bot.delete_message(chat_id=tg_id, message_id=invoice_msg_id)
            await state.update_data(invoice_msg_id=None)
    except Exception:
        pass

    # Помечаем одноразовый тест, если он был куплен
    if payload == "sub_3d":
        try:
            from database import db as user_db
            await user_db.set_trial_3d_used(str(tg_id))
        except Exception:
            pass


