"""
Админ панель - главный файл, который импортирует все модули админки.
"""
# Импортируем все роутеры из модулей
from .admin import main
from .admin import statistics
from .admin import notifications
from .admin import user_management
from .admin import config_management
from .admin import broadcast
from .admin import revenue
from .admin import system

# Создаем главный роутер
from aiogram import Router

router = Router()

# Включаем все подроутеры
router.include_router(main.router)
router.include_router(statistics.router)
router.include_router(notifications.router)
router.include_router(user_management.router)
router.include_router(config_management.router)
router.include_router(broadcast.router)
router.include_router(revenue.router)
router.include_router(system.router)
