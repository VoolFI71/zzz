"""Общие callback-обработчики (выбор тарифа, сервера, навигация)."""

from __future__ import annotations

import os
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from keyboards import keyboard
from keyboards.keyboard import (
    create_keyboard,
    create_payment_method_keyboard,
)
from database import db
from utils import get_session
import aiohttp

common_router = Router()


@common_router.callback_query(F.data.in_({"plan_1m", "plan_3m"}))
async def select_plan(callback_query: CallbackQuery, state: FSMContext) -> None:
    if callback_query.data == "plan_1m":
        days = 31
    else:
        days = 93
    await state.update_data(selected_days=days)

    # Цены для отображения методов оплаты
    star_1m = int(os.getenv("PRICE_1M_STAR", "149"))
    star_3m = int(os.getenv("PRICE_3M_STAR", "299"))
    rub_1m = int(os.getenv("PRICE_1M_RUB", "149"))
    rub_3m = int(os.getenv("PRICE_3M_RUB", "299"))

    if days == 31:
        star_amount, rub_amount = star_1m, rub_1m
    else:
        star_amount, rub_amount = star_3m, rub_3m

    await callback_query.message.edit_text(
        text=f"Выбран тариф: {days} дн. Выберите способ оплаты:",
        reply_markup=create_payment_method_keyboard(star_amount, rub_amount),
    )
    await callback_query.answer()


@common_router.callback_query(F.data.in_(["server_fi", "server_nl"]))
async def select_server(callback_query: CallbackQuery, state: FSMContext) -> None:
    if callback_query.data == "server_nl":
        await callback_query.answer("Ещё в разработке", show_alert=True)
        return
    elif callback_query.data == "server_fi":
        await state.update_data(server="fi")
        await callback_query.message.edit_text(
            text="Выберите тариф:",
            reply_markup=keyboard.create_tariff_keyboard(),
        )


@common_router.callback_query(F.data == "back")
async def go_back(callback_query: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    tg_id = callback_query.from_user.id
    current_text = (callback_query.message.text or "").lower()

    # Если на экране выбор способа оплаты — вернёмся к выбору тарифа
    if "выбран тариф" in current_text and ("оплат" in current_text or "⭐" in current_text or "₽" in current_text):
        try:
            await callback_query.message.edit_text(
                text="Выберите тариф:",
                reply_markup=keyboard.create_tariff_keyboard(),
            )
        except Exception:
            await bot.send_message(
                chat_id=tg_id,
                text="Выберите тариф:",
                reply_markup=keyboard.create_tariff_keyboard(),
            )
        await callback_query.answer()
        return

    # Если открыт экран с реальным счётом/оплатой — вернёмся к выбору способа оплаты
    # Важно: опираемся на текущий текст, чтобы не застревать из‑за старых state-значений
    if any(word in current_text for word in ["счет", "счёт", "оплат", "invoice", "управления счётом"]):
        try:
            user_state = await state.get_data()
        except Exception:
            user_state = {}
        days = int(user_state.get("selected_days", 31))
        star_1m = int(os.getenv("PRICE_1M_STAR", "149"))
        star_3m = int(os.getenv("PRICE_3M_STAR", "299"))
        rub_1m = int(os.getenv("PRICE_1M_RUB", "149"))
        rub_3m = int(os.getenv("PRICE_3M_RUB", "299"))

        if days == 31:
            star_amount, rub_amount = star_1m, rub_1m
        else:
            star_amount, rub_amount = star_3m, rub_3m

        try:
            await callback_query.message.edit_text(
                text=f"Выбран тариф: {days} дн. Выберите способ оплаты:",
                reply_markup=create_payment_method_keyboard(star_amount, rub_amount),
            )
        except Exception:
            await bot.send_message(
                chat_id=tg_id,
                text=f"Выбран тариф: {days} дн. Выберите способ оплаты:",
                reply_markup=create_payment_method_keyboard(star_amount, rub_amount),
            )
        await callback_query.answer()
        return

    if "тариф" in current_text:
        text = (
            "Вы оформляете доступ к услугам GLS VPN.\n\n"
            "- 🔐 Полная конфиденциальность и анонимность\n"
            "- ♾️ Безлимитный трафик\n"
            "- 🚀 Стабильная скорость и мгновенное подключение\n\n"
            "🌍 Доступные локации:\n"
            "├ 🇳🇱 Нидерланды — в разработке\n"
            "├ 🇩🇪 Германия — в разработке\n"
            "├ 🇺🇸 США — в разработке\n"
            "└ 🇫🇮 Финляндия — доступно"
        )
        await callback_query.message.edit_text(text=text, reply_markup=keyboard.create_server_keyboard())
    elif "страну" in current_text or "страна" in current_text:
        await bot.delete_message(chat_id=tg_id, message_id=callback_query.message.message_id)
        await bot.send_message(
            chat_id=tg_id,
            text="Выберите опцию:",
            reply_markup=create_keyboard(),
        )
    else:
        await bot.delete_message(chat_id=tg_id, message_id=callback_query.message.message_id)
        await bot.send_message(
            chat_id=tg_id,
            text="Выберите опцию:",
            reply_markup=create_keyboard(),
        )


@common_router.callback_query(F.data == "activate_balance")
async def activate_balance(callback_query: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    tg_id = str(callback_query.from_user.id)
    try:
        days = await db.get_balance_days(tg_id)
    except Exception:
        days = 0
    if days <= 0:
        await callback_query.answer("Баланс пуст", show_alert=True)
        return
    # По умолчанию используем сервер из состояния или FI
    user_data = await state.get_data()
    server = user_data.get("server") or "fi"
    data = {"time": int(days), "id": tg_id, "server": server}
    AUTH_CODE = os.getenv("AUTH_CODE")
    urlupdate = "http://fastapi:8080/giveconfig"
    try:
        session = await get_session()
        async with session.post(urlupdate, json=data, headers={"X-API-Key": AUTH_CODE}) as resp:
            if resp.status == 200:
                # Списываем баланс и уведомляем
                await db.deduct_balance_days(tg_id, int(days))
                await bot.send_message(int(tg_id), f"Активировано {days} дн. Конфиг доступен в Личном кабинете → Мои конфиги")
            elif resp.status == 409:
                await bot.send_message(int(tg_id), "Свободных конфигов нет. Попробуйте позже.")
            else:
                await bot.send_message(int(tg_id), f"Ошибка сервера ({resp.status}). Попробуйте позже.")
    except (aiohttp.ClientError, Exception):
        await bot.send_message(int(tg_id), "Ошибка сети. Попробуйте позже.")
    finally:
        try:
            await callback_query.answer()
        except Exception:
            pass

