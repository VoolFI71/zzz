import logging
from aiogram import Bot, Dispatcher
import asyncio
import os
from keyboards import keyboard
from routes import guide, start, profile, invite, tariff
from callback import callback
from database import db

API_TOKEN = str(os.getenv('TELEGRAM_TOKEN'))


logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
dp.include_routers(guide.router, start.router, tariff.router, profile.router, callback.callback_router, invite.router)


async def main():
    await db.init_db()
    # Variant B: сбрасываем накопившиеся апдейты при старте
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())