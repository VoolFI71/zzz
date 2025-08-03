from payment import payment
from database import db
from yookassa import Configuration, Payment
from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, LabeledPrice, PreCheckoutQuery, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram import Bot, Dispatcher, types

callback_router = Router()

@callback_router.callback_query()
async def process_callback_query(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    logging.info(f"Callback query received: {callback_query.data}")
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
        confirmation_url = ""
        confirmation_id = ""

        uid = uuid.uuid4()
        if callback_query.data == "buy_1":
            description = "1m"
            payment = Payment.create({
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

            confirmation_url = payment.confirmation.confirmation_url
            confirmation_id = payment.id

        elif callback_query.data == "buy_2":
            description = "3m"
            payment = Payment.create({
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

            confirmation_url = payment.confirmation.confirmation_url
            confirmation_id = payment.id

        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Перейти к оплате", url=confirmation_url)]
            ]
        )

        message = await callback_query.message.edit_text(text=f"{"Заказ на оплату успешно создан"}\n", reply_markup=reply_markup)

        await payment.check_payment_status(confirmation_id, bot, callback_query.from_user.id, payment.description, message.message_id)