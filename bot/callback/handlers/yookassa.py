"""Оплата через YooKassa: создание платежа и проверка статуса."""

from __future__ import annotations

import os
import time
import uuid
import logging
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils import check_available_configs

logger = logging.getLogger(__name__)

yookassa_router = Router()


from yookassa import Configuration, Payment

@yookassa_router.callback_query(F.data == "pay_cash")
async def pay_with_yookassa(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    user_data = await state.get_data()
    now_ts = int(time.time())
    last_click_ts = user_data.get("last_buy_click_ts")
    if last_click_ts and (now_ts - int(last_click_ts) < 3):
        await callback_query.answer("Подождите пару секунд…", show_alert=False)
        return
    await state.update_data(last_buy_click_ts=now_ts)

    server = user_data.get("server")
    if not await check_available_configs(server):
        await bot.send_message(callback_query.from_user.id, "Свободных конфигов для данного сервера нет. Попробуйте выбрать другой сервер.")
        return

    YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
    YOOKASSA_SECRET = os.getenv("YOOKASSA_SECRET_KEY")

    if not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET):
        await callback_query.answer("Платёж недоступен: YooKassa не настроена", show_alert=True)
        return

    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET

    days = int(user_data.get("selected_days", 31))
    payload = "sub_1m" if days == 31 else "sub_3m"
    # Суммы и описания из окружения с адекватными дефолтами
    price_1m = int(os.getenv("PRICE_1M_RUB", "75"))
    price_3m = int(os.getenv("PRICE_3M_RUB", "200"))
    price_3d = int(os.getenv("PRICE_3D_RUB", "5"))

    desc_1m = os.getenv("YK_DESC_1M", "Подписка GLS VPN — 1 месяц")
    desc_3m = os.getenv("YK_DESC_3M", "Подписка GLS VPN — 3 месяца")
    desc_3d = os.getenv("YK_DESC_3D", "Тестовая подписка GLS VPN — 3 дня")

    if days == 31:
        amount_rub, description = price_1m, desc_1m
    elif days == 93:
        amount_rub, description = price_3m, desc_3m
    else:
        amount_rub, description = price_3d, desc_3d

    # Чек (receipt) с обязательным блоком customer
    receipt: dict = {
        "items": [
            {
                "description": description,
                "quantity": "1.00",
                "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
                "vat_code": 1,
            }
        ]
    }
    customer: dict = {}
    # Берём из окружения, иначе подставляем технический адрес по tg_id
    _email_from_env = os.getenv("YK_RECEIPT_EMAIL")
    customer["email"] = "gleb.tula71@mail.ru"
    receipt["customer"] = customer


    try:
        payment_resp = Payment.create({
            "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": "http://t.me/glsvpn_bot"},
            "capture": True,
            "description": description,
            "metadata": {
                "tg_id": str(callback_query.from_user.id),
                "payload": payload,
            },
            "receipt": receipt,
        }, uuid.uuid4())
    except Exception as exc:
        logger.error("YooKassa create error: %s", exc)
        await callback_query.answer("Ошибка при создании платежа", show_alert=True)
        return

    # По вашему примеру: получаем URL на оплату и id транзакции
    confirmation_url = payment_resp.confirmation.confirmation_url
    confirmation_id = payment_resp.id
    await state.update_data(yookassa_payment_id=confirmation_id)

    check_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить YooKassa", url=confirmation_url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_yk")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])
    msg = await bot.send_message(
        callback_query.from_user.id,
        f"Счет создан на {amount_rub} ₽. Оплатите и нажмите \"Проверить оплату\".",
        reply_markup=check_kb,
    )
    # Сохраняем сообщение со ссылкой на оплату для последующего удаления
    try:
        await state.update_data(yookassa_msg_id=msg.message_id)
    except Exception:
        pass
    await callback_query.answer()

    # Авто-истечение (4 минуты): удаляем сообщение с кнопкой оплаты и очищаем состояние
    import asyncio as _asyncio
    async def _expire_yk_invoice() -> None:
        try:
            await _asyncio.sleep(4 * 60)
            data_state = await state.get_data()
            current_pid = data_state.get("yookassa_payment_id")
            current_msg_id = data_state.get("yookassa_msg_id")
            if current_pid == confirmation_id and current_msg_id:
                try:
                    await bot.delete_message(chat_id=callback_query.from_user.id, message_id=current_msg_id)
                except Exception:
                    pass
                try:
                    await state.update_data(yookassa_payment_id=None, yookassa_msg_id=None)
                except Exception:
                    pass
                try:
                    await bot.send_message(callback_query.from_user.id, "Счёт истёк. Если хотите, создайте новый.")
                except Exception:
                    pass
        except Exception:
            pass

    _asyncio.create_task(_expire_yk_invoice())


@yookassa_router.callback_query(F.data == "check_yk")
async def check_yookassa(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    from utils import get_session
    yk_id = (await state.get_data()).get("yookassa_payment_id")
    if not yk_id:
        await callback_query.answer("Счёт не найден", show_alert=True)
        return

    try:
        payment = Payment.find_one(yk_id)
        status = payment.status
    except Exception as exc:
        logger.error("YooKassa fetch error: %s", exc)
        await callback_query.answer("Ошибка проверки платежа", show_alert=True)
        return

    if status != "succeeded":
        await callback_query.answer("Платёж ещё не оплачен", show_alert=True)
        return

    if status == "succeeded":
        await state.update_data(yookassa_payment_id=None)
        tg_id = callback_query.from_user.id
        user_data = await state.get_data()
        server = user_data.get("server") or "fi"
        payload = payment.metadata.get("payload") if hasattr(payment, "metadata") else "sub_1m"
        days = 31 if payload == "sub_1m" else 93

        AUTH_CODE = os.getenv("AUTH_CODE")
        urlupdate = "http://fastapi:8080/giveconfig"

        session = await get_session()
        data = {"time": days, "id": str(tg_id), "server": server}
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

        # Удаляем сообщение с кнопкой оплаты, если оно есть
        try:
            data_state = await state.get_data()
            yk_msg_id = data_state.get("yookassa_msg_id")
            if yk_msg_id:
                try:
                    await bot.delete_message(chat_id=tg_id, message_id=yk_msg_id)
                except Exception:
                    pass
                await state.update_data(yookassa_msg_id=None)
        except Exception:
            pass


