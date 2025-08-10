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
from database import db as user_db

common_router = Router()


@common_router.callback_query(F.data.in_({"plan_1m", "plan_3m", "plan_3d"}))
async def select_plan(callback_query: CallbackQuery, state: FSMContext) -> None:
    if callback_query.data == "plan_3d":
        days = 3
    elif callback_query.data == "plan_1m":
        days = 31
    else:
        days = 93
    # Блокировка повторной покупки тестовой подписки (3 дня)
    if days == 3:
        tg_id = str(callback_query.from_user.id)
        await user_db.ensure_user_row(tg_id)
        if await user_db.has_used_trial_3d(tg_id):
            await callback_query.answer("Тестовую подписку можно купить только один раз", show_alert=True)
            return
    await state.update_data(selected_days=days)

    # Цены для отображения методов оплаты
    star_3d = int(os.getenv("PRICE_3D_STAR", "5"))
    star_1m = int(os.getenv("PRICE_1M_STAR", "99"))
    star_3m = int(os.getenv("PRICE_3M_STAR", "229"))
    rub_3d = int(os.getenv("PRICE_3D_RUB", "5"))
    rub_1m = int(os.getenv("PRICE_1M_RUB", "75"))
    rub_3m = int(os.getenv("PRICE_3M_RUB", "199"))

    if days == 3:
        star_amount, rub_amount = star_3d, rub_3d
    elif days == 31:
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
        await state.update_data(server="nl")
        return
    elif callback_query.data == "server_fi":
        await state.update_data(server="fi")
        await callback_query.message.edit_text(
            text="Выберите тариф:",
            reply_markup=keyboard.create_tariff_keyboard(),
        )


@common_router.callback_query(F.data == "back")
async def go_back(callback_query: CallbackQuery, bot: Bot) -> None:
    tg_id = callback_query.from_user.id
    current_text = (callback_query.message.text or "").lower()

    if "тариф" in current_text:
        await callback_query.message.edit_text(
            text="Выберите страну:",
            reply_markup=keyboard.create_server_keyboard(),
        )
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


