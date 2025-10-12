"""Оплата через YooKassa: создание платежа и проверка статуса."""

from __future__ import annotations

import os
from database import db
import time
import uuid
import logging
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from utils import check_available_configs, check_all_servers_available

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

    # Проверяем доступность серверов перед созданием платежа
    if not await check_all_servers_available():
        await callback_query.message.edit_text(
            "❌ К сожалению, сейчас не все серверы доступны для новых подписок.\n"
            "Для покупки подписки должны быть доступны все серверы.\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
            ])
        )
        await callback_query.answer()
        return

    # Проверяем, есть ли у пользователя уже АКТИВНЫЕ конфиги
    existing_configs = await db.get_active_configs_by_tg_id(callback_query.from_user.id)
    
    
    if existing_configs:
        # У пользователя есть конфиги - предлагаем продление
        await callback_query.message.edit_text(
            "У вас уже есть активная подписка! Вы хотите продлить её?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Продлить подписку", callback_data="extend_yookassa")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
            ])
        )
        await callback_query.answer()
        return
    
    # У пользователя нет конфигов - создаем новые на всех серверах
    # Используем все серверы из SERVER_ORDER (как при покупке подписки)
    env_order = os.getenv("SERVER_ORDER", "fi,ge")
    servers_to_use = [s.strip().lower() for s in env_order.split(',') if s.strip()]
    
    # Сохраняем список серверов для использования
    # Если настроены варианты (fi2, ge3), выберем по одному варианту на регион
    try:
        from utils import pick_servers_one_per_region
        selected = await pick_servers_one_per_region(servers_to_use)
    except Exception:
        selected = servers_to_use
    await state.update_data(servers_to_use=selected)

    YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
    YOOKASSA_SECRET = os.getenv("YOOKASSA_SECRET_KEY")

    if not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET):
        await callback_query.answer("Платёж недоступен: YooKassa не настроена", show_alert=True)
        return

    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET

    days = int(user_data.get("selected_days", 31))
    # Суммы и описания из окружения с адекватными дефолтами
    price_1m = int(os.getenv("PRICE_1M_RUB", "100"))
    price_3m = int(os.getenv("PRICE_3M_RUB", "250"))
    price_6m = int(os.getenv("PRICE_6M_RUB", "450"))

    desc_1m = os.getenv("YK_DESC_1M", "Подписка GLS VPN — 1 месяц")
    desc_3m = os.getenv("YK_DESC_3M", "Подписка GLS VPN — 3 месяца")
    desc_6m = os.getenv("YK_DESC_6M", "Подписка GLS VPN — 6 месяцев")
    desc_12m = os.getenv("YK_DESC_12M", "Подписка GLS VPN — 12 месяцев")

    if days == 31:
        payload = "sub_1m"
        amount_rub, description = price_1m, desc_1m
    elif days == 93:
        payload = "sub_3m"
        amount_rub, description = price_3m, desc_3m
    elif days == 180:
        payload = "sub_6m"
        amount_rub, description = price_6m, desc_6m
    else:
        payload = "sub_1m"
        amount_rub, description = price_1m, desc_1m

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
            "confirmation": {"type": "redirect", "return_url": "https://t.me/glsvpn_bot"},
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
        [InlineKeyboardButton(text="❌ Отменить счёт", callback_data="cancel_yk_invoice")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")],
    ])
    msg = await bot.send_message(
        callback_query.from_user.id,
        f"Счёт создан на {amount_rub} ₽. Оплатите и нажмите \"Проверить оплату\".",
        reply_markup=check_kb,
    )
    # Сохраняем сообщение со ссылкой на оплату для последующего удаления
    try:
        await state.update_data(yookassa_msg_id=msg.message_id)
    except Exception:
        pass
    await callback_query.answer()
    # Пишем агрегат сразу после создания счёта не будем — считаем только по факту успешной оплаты

    # Авто-истечение (10 минут): удаляем сообщение с кнопкой оплаты и очищаем состояние
    import asyncio as _asyncio
    async def _expire_yk_invoice() -> None:
        try:
            await _asyncio.sleep(10 * 60)
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


@yookassa_router.callback_query(F.data == "cancel_yk_invoice")
async def cancel_yk_invoice(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    tg_id = callback_query.from_user.id
    try:
        data_state = await state.get_data()
        yk_msg_id = data_state.get("yookassa_msg_id")
        if yk_msg_id:
            try:
                await bot.delete_message(chat_id=tg_id, message_id=yk_msg_id)
            except Exception:
                pass
            await state.update_data(yookassa_msg_id=None, yookassa_payment_id=None)
    except Exception:
        pass
    # Вернём клавиатуру способов оплаты
    try:
        days = int((await state.get_data()).get("selected_days", 31))
        star_1m = int(os.getenv("PRICE_1M_STAR", "100"))
        star_3m = int(os.getenv("PRICE_3M_STAR", "250"))
        star_6m = int(os.getenv("PRICE_6M_STAR", "450"))
        rub_1m = int(os.getenv("PRICE_1M_RUB", "100"))
        rub_3m = int(os.getenv("PRICE_3M_RUB", "250"))
        rub_6m = int(os.getenv("PRICE_6M_RUB", "450"))

        if days == 31:
            star_amount, rub_amount = star_1m, rub_1m
        elif days == 93:
            star_amount, rub_amount = star_3m, rub_3m
        elif days == 180:
            star_amount, rub_amount = star_6m, rub_6m
        else:
            star_amount, rub_amount = star_1m, rub_1m
        from keyboards.keyboard import create_payment_method_keyboard
        await bot.send_message(
            tg_id,
            f"Выбран тариф: {days} дн. Выберите способ оплаты:",
            reply_markup=create_payment_method_keyboard(star_amount, rub_amount),
        )
    except Exception:
        pass
    await callback_query.answer("Счёт отменён")


@yookassa_router.callback_query(F.data == "check_yk")
@yookassa_router.callback_query(F.data == "check_yookassa")
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
        payload = payment.metadata.get("payload") if hasattr(payment, "metadata") else "sub_1m"
        payload_to_days = {"sub_1m": 31, "sub_3m": 93, "sub_6m": 180, "sub_12m": 365}
        days = payload_to_days.get(payload, 31)

        # Проверяем, есть ли у пользователя уже АКТИВНЫЕ конфиги
        existing_configs = await db.get_active_configs_by_tg_id(tg_id)
        
        if existing_configs:
            # Продлеваем существующие конфиги
            await extend_existing_configs_yookassa(tg_id, days, bot)
        else:
            # Выдаем конфиги на ранее выбранных серверах (по одному на регион)
            data_state = await state.get_data()
            servers_to_use = data_state.get("servers_to_use")
            if not servers_to_use:
                import os
                server_order_env = os.getenv("SERVER_ORDER", "fi,ge")
                fallback = [s.strip().lower() for s in server_order_env.split(',') if s.strip()]
                try:
                    from utils import pick_servers_one_per_region
                    servers_to_use = await pick_servers_one_per_region(fallback)
                except Exception:
                    servers_to_use = fallback
            await give_configs_on_all_servers_yookassa(tg_id, days, servers_to_use, bot)
        
        # Записываем платеж в статистику
        amount = payment.amount.value if hasattr(payment.amount, 'value') else 0
        await db.mark_payment(tg_id, days)
        await db.add_rub_payment(amount)
        
        # Начисляем бонус рефералу
        inviter_tg_id = await db.get_referrer_id(str(tg_id))
        if inviter_tg_id:
            try:
                # Начисляем бонусные дни (например, 2 дня)
                BONUS_DAYS = int(days//10)
                await db.add_balance_days(str(inviter_tg_id), BONUS_DAYS)
                try:
                    await bot.send_message(int(inviter_tg_id),
                                        f"Ваш реферал оплатил подписку — вам начислено {BONUS_DAYS} дня(ей) бонуса. Вы можете активировать их в личном кабинете")
                except Exception:
                    pass
            except Exception as exc:
                logger.error("Ошибка начисления бонуса пригласителю %s: %s", inviter_tg_id, exc)
        
        # Уведомляем админа
        try:
            admin_id = 746560409
            if admin_id:
                at_username = (f"@{callback_query.from_user.username}" if getattr(callback_query.from_user, "username", None) else "—")
                if existing_configs:
                    # Продление подписки
                    await bot.send_message(admin_id, f"Продлена подписка через YooKassa: user_id={tg_id}, user={at_username}, срок={days} дн.")
                else:
                    # Новая подписка
                    await bot.send_message(admin_id, f"Оплачена подписка через YooKassa: user_id={tg_id}, user={at_username}, срок={days} дн.")
        except Exception:
            pass

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


async def give_configs_on_all_servers_yookassa(tg_id: int, days: int, servers: list, bot: Bot) -> None:
    """Выдает конфиги на всех указанных серверах для нового пользователя (YooKassa)."""
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
        await bot.send_message(tg_id, f"✅ Оплата прошла успешно! \n\nПолучить подписку можно в Личном кабинете → Мои подключения")
    
    if failed_servers:
        await bot.send_message(tg_id, f"⚠️ Не удалось создать конфиги на серверах: {', '.join(failed_servers)}")


async def extend_existing_configs_yookassa(tg_id: int, days: int, bot: Bot) -> None:
    """Продлевает существующие конфиги пользователя (YooKassa)."""
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
            logger.error(f"Failed to extend config {user_code}: {e}")
            failed_configs.append(user_code)
    
    # Уведомляем пользователя о результате
    if success_count > 0:
        await bot.send_message(tg_id, f"✅ Оплата прошла успешно! Подписка продлена на {success_count} конфигах.\n\nПолучить подписку можно в Личном кабинете → Мои подключения")
    
    if failed_configs:
        await bot.send_message(tg_id, f"⚠️ Не удалось продлить {len(failed_configs)} конфигов")


@yookassa_router.callback_query(F.data == "extend_yookassa")
async def extend_yookassa_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик продления подписки через YooKassa."""
    tg_id = callback_query.from_user.id
    
    # Проверяем доступность серверов перед созданием платежа для продления
    if not await check_all_servers_available():
        await callback_query.message.edit_text(
            "❌ К сожалению, сейчас не все серверы доступны для продления подписок.\n"
            "Для продления подписки должны быть доступны все серверы.\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
            ])
        )
        await callback_query.answer()
        return
    
    user_data = await state.get_data()
    days = int(user_data.get("selected_days", 31))

    # Создаем платеж для продления
    price_1m = int(os.getenv("PRICE_1M_RUB", "100"))
    price_3m = int(os.getenv("PRICE_3M_RUB", "250"))
    price_6m = int(os.getenv("PRICE_6M_RUB", "450"))
    if days == 31:
        payload = "sub_1m"; amount = price_1m
    elif days == 93:
        payload = "sub_3m"; amount = price_3m
    elif days == 180:
        payload = "sub_6m"; amount = price_6m
    else:
        payload = "sub_1m"; amount = price_1m
    
    YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
    YOOKASSA_SECRET = os.getenv("YOOKASSA_SECRET_KEY")
    
    if not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET):
        await callback_query.answer("Платёж недоступен: YooKassa не настроена", show_alert=True)
        return
    
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET
    
    try:
        payment = Payment.create({
            "amount": {"value": str(amount), "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": "https://t.me/your_bot"},
            "capture": True,
            "description": f"Продление подписки GLS VPN — {days} дн.",
            "metadata": {"payload": payload},
            "receipt": {
                "customer": {"email": f"gleb.tula71@mail.ru"},
                "items": [{
                    "description": f"Продление подписки GLS VPN — {days} дн.",
                    "amount": {"value": str(amount), "currency": "RUB"},
                    "vat_code": 1,
                    "quantity": "1"
                }]
            }
        })
        
        await state.update_data(yookassa_payment_id=payment.id)
        msg = await callback_query.message.edit_text(
            f"💳 <b>Продление подписки GLS VPN — {days} дн.</b>\n\n"
            f"Сумма: {amount} ₽\n\n"
            f"Нажмите кнопку ниже для оплаты:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment.confirmation.confirmation_url)],
                [InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_yookassa")],
                [InlineKeyboardButton(text="❌ Отменить счёт", callback_data="cancel_yk_invoice")]
            ]),
            parse_mode="HTML"
        )
        try:
            await state.update_data(yookassa_msg_id=msg.message_id)
        except Exception:
            pass
        await callback_query.answer("Счёт для продления создан!")
        # Авто-истечение (10 минут) для продления
        import asyncio as _asyncio
        async def _expire_yk_invoice_renewal() -> None:
            try:
                await _asyncio.sleep(10 * 60)
                data_state = await state.get_data()
                current_pid = data_state.get("yookassa_payment_id")
                current_msg_id = data_state.get("yookassa_msg_id")
                if current_pid == payment.id and current_msg_id:
                    try:
                        await bot.delete_message(chat_id=tg_id, message_id=current_msg_id)
                    except Exception:
                        pass
                    try:
                        await state.update_data(yookassa_payment_id=None, yookassa_msg_id=None)
                    except Exception:
                        pass
                    try:
                        await bot.send_message(tg_id, "Счёт истёк. Если хотите, создайте новый.")
                    except Exception:
                        pass
            except Exception:
                pass
        _asyncio.create_task(_expire_yk_invoice_renewal())
    except Exception as e:
        logger.error(f"Failed to create YooKassa payment: {e}")
        await callback_query.answer("Ошибка создания счёта", show_alert=True)


