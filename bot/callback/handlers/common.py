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
from utils import pick_first_available_server
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
    star_3m = int(os.getenv("PRICE_3M_STAR", "349"))
    rub_1m = int(os.getenv("PRICE_1M_RUB", "149"))
    rub_3m = int(os.getenv("PRICE_3M_RUB", "349"))


    if days == 31:
        star_amount, rub_amount = star_1m, rub_1m
    else:
        star_amount, rub_amount = star_3m, rub_3m

    await callback_query.message.edit_text(
        text=f"Выбран тариф: {days} дн. Выберите способ оплаты:",
        reply_markup=create_payment_method_keyboard(star_amount, rub_amount),
    )
    await callback_query.answer()


@common_router.callback_query(F.data.startswith("server_"))
async def select_server(callback_query: CallbackQuery, state: FSMContext) -> None:
    # Accept any callback in the form "server_<code>" and persist the code
    data = callback_query.data or ""
    server_code = data.split("_", 1)[1].lower() if "_" in data else ""
    if server_code:
        await state.update_data(server=server_code)
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
        star_3m = int(os.getenv("PRICE_3M_STAR", "349"))
        rub_1m = int(os.getenv("PRICE_1M_RUB", "149"))
        rub_3m = int(os.getenv("PRICE_3M_RUB", "349"))


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
    # Временно отключена активация конфигов
    await callback_query.answer(
        "🚧 Активация конфигов временно недоступна\n\n"
        "В данный момент мы проводим технические работы.\n"
        "Попробуйте позже.",
        show_alert=True
    )

