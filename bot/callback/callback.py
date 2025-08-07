"""Callback-обработчики покупок с помощью Telegram Stars.

В этой версии убраны зависимости от YooKassa. Бот принимает оплату
встроенными "звёздами" Telegram и получает событие `successful_payment`
сразу после подтверждения.
"""

from __future__ import annotations

import logging
import os
import aiohttp
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from database import db  # локальный модуль
from keyboards import keyboard
from keyboards.keyboard import create_keyboard
from utils import check_available_configs

logger = logging.getLogger(__name__)

callback_router = Router()

# ---------------------------------------------------------------------------
# Inline-callback для выбора тарифа и создания счёта Stars
# ---------------------------------------------------------------------------

@callback_router.callback_query()
async def process_callback_query(
    callback_query: CallbackQuery,
    state: FSMContext,
    bot: Bot,
) -> None:  # noqa: D401 – коллбек-функция
    tg_id = callback_query.from_user.id

    # Покупка тарифов
    if callback_query.data in {"buy_1", "buy_2"}:
        # Проверка email больше не требуется

        # Проверяем свободные конфиги
        user_data = await state.get_data()
        server = user_data.get("server")
        if not await check_available_configs(server):
            await bot.send_message(tg_id, "Свободных конфигов для данного сервера нет. Попробуйте выбрать другой сервер.")
            return
        provider_token = ""
        # provider_token = os.getenv("STARS_TOKEN")
        # if not provider_token:
        #     await callback_query.answer("Платёж недоступен: STARS_TOKEN не настроен", show_alert=True)
        #     return

        # Удаляем сообщение с кнопками тарифа, чтобы не оставалось лишнего UI
        try:
            await bot.delete_message(chat_id=tg_id, message_id=callback_query.message.message_id)
        except Exception:
            pass

        # Создаём счёт и запоминаем id сообщения с инвойсом для последующего удаления
        if callback_query.data == "buy_1":
            invoice_msg = await bot.send_invoice(
                chat_id=tg_id,
                title="Подписка на 1 месяц",
                description="Доступ к сервису на 1 месяц",
                payload="sub_1m",
                provider_token=provider_token,
                currency="XTR",
                prices=[LabeledPrice(label="XTR", amount=99)],
                max_tip_amount=0,
            )
        else:  # buy_2
            invoice_msg = await bot.send_invoice(
                chat_id=tg_id,
                title="Подписка на 3 месяца",
                description="Доступ к сервису на 3 месяца",
                payload="sub_3m",
                provider_token=provider_token,
                currency="XTR",
                prices=[LabeledPrice(label="XTR", amount=249)],
                max_tip_amount=0,
            )
        try:
            await state.update_data(invoice_msg_id=invoice_msg.message_id)
        except Exception:
            pass
        await callback_query.answer("Создаём счёт для оплаты...")
        return

    # Обработка выбора сервера
    if callback_query.data in ["server_fi", "server_nl"]:
        if callback_query.data == "server_nl":
            await callback_query.answer("Ещё в разработке", show_alert=True)
            await state.update_data(server="nl")
            return
        elif callback_query.data == "server_fi":
            await state.update_data(server="fi")
            await callback_query.message.edit_text(
                text="Выберите тариф:",
                reply_markup=keyboard.create_tariff_keyboard()
            )
            return

    # Обработка кнопки "Назад"
    if callback_query.data == "back":
        current_text = (callback_query.message.text or "").lower()
        
        if "тариф" in current_text:
            # На экране тарифов → вернуться к выбору страны
            await callback_query.message.edit_text(
                text="Выберите страну:",
                reply_markup=keyboard.create_server_keyboard(),
            )
        elif "страну" in current_text or "страна" in current_text:
            # На экране выбора страны → главное меню
            await bot.delete_message(chat_id=tg_id, message_id=callback_query.message.message_id)
            await bot.send_message(
                chat_id=tg_id,
                text="Выберите опцию:",
                reply_markup=create_keyboard(),
            )
        else:
            # Для всех остальных случаев – главное меню
            await bot.delete_message(chat_id=tg_id, message_id=callback_query.message.message_id)
            await bot.send_message(
                chat_id=tg_id,
                text="Выберите опцию:",
                reply_markup=create_keyboard(),
            )
        return


# ---------------------------------------------------------------------------
# Telegram Stars: подтверждение и успешная оплата
# ---------------------------------------------------------------------------

@callback_router.pre_checkout_query(lambda _: True)
async def pre_checkout_query_handler(
    pre_checkout_query: PreCheckoutQuery,
    bot: Bot,
) -> None:
    """Отвечаем Telegram, что предварительная проверка прошла успешно."""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@callback_router.message(F.successful_payment)
async def successful_payment_handler(message: Message, bot: Bot, state: FSMContext) -> None:
    """Обрабатываем успешную оплату и выдаём конфиг пользователю."""
    tg_id = message.from_user.id
    payload = message.successful_payment.invoice_payload

    days: int
    if payload == "sub_1m":
        days = 31
    elif payload == "sub_3m":
        days = 93
    else:
        await bot.send_message(tg_id, "Неизвестный тип подписки. Сообщите поддержке.")
        return

    # Вытаскиваем выбранный сервер из FSM (если пользователь выбирал)
    user_data = await state.get_data()
    server = user_data.get("server") or "fi"

    data = {"time": days, "id": str(tg_id), "server": server}
    AUTH_CODE = os.getenv("AUTH_CODE")
    urlupdate = "http://fastapi:8080/giveconfig"

    from utils import get_session
    session = await get_session()
    try:
        async with session.post(urlupdate, json=data, headers={"X-API-Key": AUTH_CODE}) as resp:
                if resp.status == 200:
                    await bot.send_message(tg_id, "Подписка активирована! Конфиг доступен в личном кабинете.")
                elif resp.status == 409:
                    await bot.send_message(tg_id, "Свободных конфигов нет. Свяжитесь с поддержкой.")
                else:
                    await bot.send_message(tg_id, f"Ошибка сервера ({resp.status}). Попробуйте позже.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Ошибка обращения к FastAPI: %s", exc)
        await bot.send_message(tg_id, "Ошибка сети. Попробуйте позже или напишите в поддержку.")

    # Удаляем инвойс после успешной оплаты, если он есть в состоянии
    try:
        data_state = await state.get_data()
        invoice_msg_id = data_state.get("invoice_msg_id")
        if invoice_msg_id:
            await bot.delete_message(chat_id=tg_id, message_id=invoice_msg_id)
            await state.update_data(invoice_msg_id=None)
    except Exception:
        pass
