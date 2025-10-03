"""Общие callback-обработчики (выбор тарифа, сервера, навигация)."""

from __future__ import annotations

import os
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from keyboards import keyboard
from keyboards.keyboard import (
    create_keyboard,
    create_payment_method_keyboard,
)
from database import db
from utils import get_session, check_available_configs, check_all_servers_available
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
            "├ 🇺🇸 США — в разработке\n"
            "├ 🇩🇪 Германия — в разработке\n"
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

    # Проверяем доступность серверов перед активацией бонусных дней
    if not await check_all_servers_available():
        await callback_query.message.edit_text(
            "❌ К сожалению, сейчас не все серверы доступны для активации бонусных дней.\n"
            "Для активации дней должны быть доступны все серверы.\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
            ])
        )
        await callback_query.answer()
        return
    # Проверяем, есть ли у пользователя уже АКТИВНЫЕ конфиги
    existing_configs = await db.get_active_configs_by_tg_id(tg_id)
    
    if existing_configs:
        # Продлеваем существующие конфиги
        await extend_existing_configs_balance(tg_id, days, bot)
    else:
        # Выдаем конфиги на всех серверах из SERVER_ORDER
        env_order = os.getenv("SERVER_ORDER", "fi,ge")
        servers_to_use = [s.strip().lower() for s in env_order.split(',') if s.strip()]
        
        await give_configs_on_all_servers_balance(tg_id, days, servers_to_use, bot)
    
    try:
        await callback_query.answer()
    except Exception:
        pass


async def give_configs_on_all_servers_balance(tg_id: int, days: int, servers: list, bot: Bot) -> None:
    """Выдает конфиги на всех указанных серверах для нового пользователя (активация баланса)."""
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
            print(f"Failed to create config on server {server}: {e}")
            failed_servers.append(server)
    
    # Списываем баланс только если хотя бы один конфиг создан
    if success_count > 0:
        await db.deduct_balance_days(tg_id, int(days))
        
        # Уведомляем пользователя о результате
        try:
            sub_key = await db.get_or_create_sub_key(str(tg_id))
            base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
            sub_url = f"{base}/subscription/{sub_key}"
            await bot.send_message(tg_id, f"✅ Активировано {days} дн. на {success_count} серверах!\n\nВаша ссылка подписки: {sub_url}")
        except Exception:
            await bot.send_message(tg_id, f"✅ Активировано {days} дн. на {success_count} серверах!")
        
        # Уведомляем администратора о активации бонусных дней
        try:
            admin_id = 746560409
            username = "—"  # Можно добавить получение username если нужно
            await bot.send_message(
                admin_id,
                f"🎁 Активация бонусных дней: user_id={tg_id}, дней={days}, серверов={success_count}"
            )
        except Exception:
            pass
    
    if failed_servers:
        await bot.send_message(tg_id, f"⚠️ Не удалось создать конфиги на серверах: {', '.join(failed_servers)}")


async def extend_existing_configs_balance(tg_id: int, days: int, bot: Bot) -> None:
    """Продлевает существующие конфиги пользователя (активация баланса)."""
    from utils import get_session
    import aiohttp
    
    AUTH_CODE = os.getenv("AUTH_CODE")
    urlextend = "http://fastapi:8080/extendconfig"
    session = await get_session()
    
    # Получаем все АКТИВНЫЕ конфиги пользователя
    existing_configs = await db.get_active_configs_by_tg_id(tg_id)
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
            print(f"Failed to extend config {user_code}: {e}")
            failed_configs.append(user_code)
    
    # Уведомляем пользователя о результате
    if success_count > 0:
        # Списываем баланс и уведомляем
        await db.deduct_balance_days(tg_id, int(days))
        await bot.send_message(int(tg_id), f"✅ Продлено на {success_count} конфигах! Конфиги доступны в Личном кабинете → Мои конфиги")
        
        # Уведомляем администратора о активации бонусных дней
        try:
            admin_id = 746560409
            await bot.send_message(
                admin_id,
                f"🎁 Продление бонусных дней: user_id={tg_id}, дней={days}, конфигов={success_count}"
            )
        except Exception:
            pass
    
    if failed_configs:
        await bot.send_message(int(tg_id), f"⚠️ Не удалось продлить {len(failed_configs)} конфигов")

