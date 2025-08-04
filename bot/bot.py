import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import uuid
from email_validator import validate_email, EmailNotValidError
import os

from keyboards import keyboard
from routes import guide, start, profile, invite, tariff
from callback import callback
from database import db
from payment import payment as pay
from states import Form

from yookassa import Configuration, Payment

Configuration.account_id = os.getenv('ACCOUNT_ID')
Configuration.secret_key = str(os.getenv('SECRET_KEY'))
API_TOKEN = str(os.getenv('TELEGRAM_TOKEN'))

urlupdate = "http://77.110.108.194:8080/giveconfig"
#urlupdate = "http://fastapi:8080/giveconfig"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
dp.include_routers(guide.router, start.router, tariff.router, profile.router, callback.callback_router, invite.router)

@dp.message(Form.waiting_for_email)
async def handle_email_input(message: Message, state: FSMContext) -> None:
    tg_id = message.from_user.id
    email_input = message.text
    try:
        valid = validate_email(email_input) 
        email = valid.email
        await db.insert_email(tg_id, email)  
        await message.reply("Email успешно сохранен!", reply_markup=keyboard.create_tariff_keyboard())
    except EmailNotValidError as e:
        await message.reply(f"Ошибка: {str(e)}. Пожалуйста, введите корректный email, это необходимо для отправки чека на вашу почту.")
        return
    await state.set_state(None) 


async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())