import logging
from aiogram import Bot, Dispatcher
import asyncio
import os
from keyboards import keyboard
from routes import guide, start, profile, invite, tariff, admin
from routes.admin import advanced_broadcast, monitoring
from services.broadcast_service import BroadcastService
from services.monitoring_service import MonitoringService
from callback import callback
from database import db
from middlewares.throttling import ThrottlingMiddleware

API_TOKEN = str(os.getenv('TELEGRAM_TOKEN'))


logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
    # Anti-flood / throttling middleware
dp.message.middleware(ThrottlingMiddleware(default_window=1.5, default_burst=3))
dp.callback_query.middleware(ThrottlingMiddleware(default_window=1.0, default_burst=4))
dp.include_routers(guide.router, start.router, tariff.router, profile.router, callback.callback_router, invite.router, admin.router, advanced_broadcast.router, monitoring.router)


async def main():
    await db.init_db()
    
    # Инициализация сервиса рассылок
    broadcast_service = BroadcastService(bot)
    await broadcast_service.init_database()
    
    # Инициализация сервиса мониторинга
    monitoring_service = MonitoringService()
    await monitoring_service.start_monitoring()
    
    # Передаем сервис мониторинга в модуль
    monitoring.init_monitoring_service(monitoring_service)
    
    # Variant B: сбрасываем накопившиеся апдейты при старте
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())