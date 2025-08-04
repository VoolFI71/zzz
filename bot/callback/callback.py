from payment import payment as pay
from database import db
from yookassa import Configuration, Payment
from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, LabeledPrice, PreCheckoutQuery, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram import Bot, Dispatcher, types
import aiohttp
import os
import uuid
import logging
logger = logging.getLogger(__name__)
from states import Form
from keyboards.keyboard import create_keyboard
from utils import check_available_configs

callback_router = Router()

AUTH_CODE = os.getenv("AUTH_CODE")

@callback_router.callback_query()
async def process_callback_query(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    logger.info(f"Callback query received: {callback_query.data}")
    tg_id = callback_query.from_user.id     

    if callback_query.data == "back":
        await bot.delete_message(chat_id=tg_id, message_id=callback_query.message.message_id)
        await bot.send_message(
            chat_id=callback_query.from_user.id,
            text="Выберите опцию:",
            reply_markup=create_keyboard()  
        )
        return 

    email = await db.get_email(tg_id)
    if email is None:
        await bot.send_message(tg_id, "Пожалуйста, введите корректный email для отправки чеков на почту:")
        await state.set_state(Form.waiting_for_email)
    else:
        # Проверяем наличие свободных конфигов только если у пользователя есть email
        if callback_query.data in ["buy_1", "buy_2"]:
            configs_available = await check_available_configs()
            if not configs_available:
                await bot.send_message(
                    tg_id, 
                    "К сожалению, в данный момент нет свободных конфигураций. Попробуйте позже или обратитесь в поддержку."
                )
                return
        confirmation_url = ""
        confirmation_id = ""

        uid = uuid.uuid4()
        if callback_query.data == "buy_1":
            description = "1m"
            payment_resp = Payment.create({
                "amount": {
                    "value": 99,
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/godnet_vpnbot"
                },
                "capture": True,
                "description": description,
                "receipt": {
                    "customer": {
                        "email": email
                    },
                    "items": [
                        {
                            "description": "Подписка на 1 месяц",
                            "quantity": 1,
                            "amount": {
                                "value": "99.00",
                                "currency": "RUB"
                            },
                            "vat_code": 1
                        }
                    ]
                }
            }, uid)

            confirmation_url = payment_resp.confirmation.confirmation_url
            confirmation_id = payment_resp.id

        elif callback_query.data == "buy_2":
            description = "3m"
            payment_resp = Payment.create({
                "amount": {
                    "value": 199,
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/godnet_vpnbot"
                },
                "capture": True,
                "description": description,
                "receipt": {
                    "customer": {
                        "email": email
                    },
                    "items": [
                        {
                            "description": "Подписка на 3 месяца",
                            "quantity": 1,
                            "amount": {
                                "value": "199.00",
                                "currency": "RUB"
                            },
                            "vat_code": 1
                        }
                    ]
                }
            }, uid)

            confirmation_url = payment_resp.confirmation.confirmation_url
            confirmation_id = payment_resp.id

        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Перейти к оплате", url=confirmation_url)]
            ]
        )

        message = await callback_query.message.edit_text(text=f"{"Заказ на оплату успешно создан"}\n", reply_markup=reply_markup)

        await pay.check_payment_status(confirmation_id, bot, callback_query.from_user.id, description, message.message_id)