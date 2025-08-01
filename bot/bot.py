import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, LabeledPrice, PreCheckoutQuery, Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram import F
from aiogram.fsm.state import State, StatesGroup
from aiogram import Router
from datetime import datetime, timedelta
import aiosqlite
import asyncio
import requests
import json
import aiohttp
import time
from yookassa import Configuration, Payment
import uuid
from email_validator import validate_email, EmailNotValidError
import os

Configuration.account_id = os.getenv('ACCOUNT_ID')
Configuration.secret_key = str(os.getenv('SECRET_KEY'))
API_TOKEN = str(os.getenv('TELEGRAM_TOKEN'))
# urlupdate = "http://77.110.108.194:8080/giveconfig"
urlupdate = "http://fastapi:8080/giveconfig"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_email = State()

async def init_db():
    async with aiosqlite.connect("emails.db") as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS email (
                tg_id TEXT UNIQUE,
                email TEXT
            )
        ''')
        await conn.commit()

async def get_email(tg_id):
    """Получить email пользователя по его tg_id из базы данных."""
    async with aiosqlite.connect("emails.db") as conn:
        async with conn.execute('SELECT email FROM email WHERE tg_id = ?', (tg_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def insert_email(tg_id, email):
    """Сохранить email пользователя в базе данных."""
    try:
        async with aiosqlite.connect("emails.db") as conn:
            async with conn.execute('INSERT INTO email (tg_id, email) VALUES (?, ?)', (tg_id, email)):
                await conn.commit()
    except aiosqlite.IntegrityError:
        print(f"Ошибка: tg_id '{tg_id}' уже существует.")
    except aiosqlite.Error as e:
        print(f"Ошибка при вставке данных: {e}")

def create_keyboard():
    kb_list = [
        [KeyboardButton(text="Выбрать тариф"), KeyboardButton(text="Личный кабинет")],
        [KeyboardButton(text="Инструкция⚙️")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=True)
    return keyboard

def create_tariff_keyboard():
    kb_list = [
        [InlineKeyboardButton(text="Купить на 1 месяц - 99 Рублей💰", callback_data="buy_1")],
        [InlineKeyboardButton(text="Купить на 3 месяца - 199 Рублей💰", callback_data="buy_2")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]

    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_list)
    return keyboard

def create_settings_keyboard():
    kb_list = [
        [KeyboardButton(text="Установка на Телефон"), KeyboardButton(text="Установка на PC")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, one_time_keyboard=True)
    return keyboard

@dp.message(Command('start'))
async def start_command(message: types.Message):
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=create_keyboard())

@dp.message(F.text == "Инструкция⚙️")
async def guide_command(message: types.Message):
    await message.answer("Выберите способ установки:", reply_markup=create_settings_keyboard())

@dp.message(F.text == "Установка на Телефон")
async def tel_guide_command(message: types.Message):
    await message.answer(
        "Установка подключения на [Android](https://play.google.com/store/apps/details?id=com.v2raytun.android) и [iOS](https://apps.apple.com/ru/app/v2raytun/id6476628951) идентична. Чтобы подключиться к серверу необходимо установить приложение v2RayTun. Скопировать конфиг подключения из личного кабинета в боте. Вставить конфиг из буфера обмена в установленном приложении и подключиться.",
        reply_markup=create_keyboard(),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

@dp.message(F.text == "Установка на PC")
async def pc_guide_command(message: types.Message):
    await message.answer("Чтобы подключиться к серверу необходимо установить приложение v2RayN [IOS](https://apps.apple.com/ru/app/v2raytun/id6476628951), [Windows, Linux](https://github.com/2dust/v2rayN/releases/download/7.13.2/v2rayN-windows-64.zip). Простая установка для всех устройств [Amneziavpn](https://amnezia.app/ru/downloads). Скопировать конфиг подключения из личного кабинета в боте. Вставить конфиг из буфера обмена в установленном приложении и подключиться", 
    reply_markup=create_keyboard(),
    parse_mode='Markdown',
    disable_web_page_preview=True
    )
    
@dp.message(F.text == "Выбрать тариф")
async def choose_tariff(message: types.Message):
    await message.answer("Выберите тариф:", reply_markup=create_tariff_keyboard())

@dp.message(Form.waiting_for_email)
async def handle_email_input(message: Message, state: FSMContext) -> None:
    tg_id = message.from_user.id
    email_input = message.text
    try:
        valid = validate_email(email_input) 
        email = valid.email
        await insert_email(tg_id, email)  
        await message.reply("Email успешно сохранен!", reply_markup=create_tariff_keyboard())
    except EmailNotValidError as e:
        await message.reply(f"Ошибка: {str(e)}. Пожалуйста, введите корректный email, это необходимо для отправки чека на вашу почту.")
        return
    await state.set_state(None) 

async def check_payment_status(payment_id, bot, user_id, description, message_id):
    i = 0
    while i < 46:
        await asyncio.sleep(10) 
        try: 
            data = {}
            if description == "1m":
                data["time"] = 1
            elif description == "3m":
                data["time"] = 3
            data["id"] = str(user_id)

            payment = Payment.find_one(str(payment_id))
        
            if payment.status == "succeeded" and payment.paid:
                await bot.send_message(
                    chat_id=user_id,
                    text="Успешно! Ваш платеж был подтвержден."
                )
                data["auth"] = "+7999999999999999999"
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(urlupdate, json=data) as response:
                            if response.status == 200:
                                await bot.send_message(user_id, "Конфиг для подключения можно найти в личном кабинете.")
                            elif response.status == 409:
                                await bot.send_message(user_id, "Ошибка при получении конфига. Свободных конфигов нет. Обратитесь в поддержку.")
                            else:
                                await bot.send_message(user_id, "Ошибка при получении конфига. Обратитесь в поддержку. Номер ошибки 1.")
                    except Exception as e:
                        await bot.send_message(user_id, "Ошибка при получении конфига. Обратитесь в поддержку. Номер ошибки 2.")
                        print(f"Exception occurred: {e}")

                await bot.delete_message(chat_id=user_id, message_id=message_id)
                break
                
            elif payment.status == "canceled":
                await bot.send_message(
                    chat_id=user_id,
                    text="Платеж не был подтвержден. Попробуйте снова."
                )
                await bot.delete_message(chat_id=user_id, message_id=message_id)

            elif payment.status == "pending":
                pass
                # await bot.send_message(
                #     chat_id=user_id,
                #     text="Ожидание оплаты."
                # )
        except Exception as e:
            print(e)
        i+=1

@dp.callback_query()
async def process_callback_query(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await init_db()
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

    email = await get_email(tg_id)
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

        await check_payment_status(confirmation_id, bot, callback_query.from_user.id, payment.description, message.message_id)

@dp.message(F.text == "Личный кабинет")
async def my_account(message: types.Message):
    user_id = message.from_user.id
    url = f"http://fastapi:8080/usercodes/{user_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if response_data:
                        for i, user in enumerate(response_data, start=1):
                            remaining_seconds = user['time_end'] - int(time.time()) 
                            if remaining_seconds <= 0 :
                                await message.answer(f"Время действия конфига истекло \n")
                            else: 
                                exptime = remaining_seconds / 3600
                                await message.answer(f"Конфиг {i}. Оставшееся время действия: {exptime:.2f} часов \n")
                            response_message = (
                                f"vless://{user['user_code']}@77.110.108.194:443?"
                                "security=reality&encryption=none&pbk=bMhOMGZho4aXhfoxyu7D9ZjVnM-02bR9dKBfIMMTVlc&"
                                "headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&sni=google.com&sid=094e39c18a0e44#godnetvpn.\n"
                            )
                            await message.answer(response_message + "\n", reply_markup=create_keyboard())
                    else:
                        await message.answer("У вас нет конфигов")
                else:
                    error_message = await response.json()
                    await message.answer(f"Ошибка: {error_message.get('detail', 'Неизвестная ошибка')}", reply_markup=create_keyboard())
    except aiohttp.ClientError as e:
        await message.answer(f"Ошибка соединения: {str(e)}", reply_markup=create_keyboard())
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}", reply_markup=create_keyboard())

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())