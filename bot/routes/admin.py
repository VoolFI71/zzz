"""
Админ панель - главный файл, который импортирует все модули админки.
"""
# Импортируем все роутеры из модулей
from routes.admin.main import router as main_router
from routes.admin.statistics import router as statistics_router
from routes.admin.notifications import router as notifications_router
from routes.admin.user_management import router as user_management_router
from routes.admin.config_management import router as config_management_router
from routes.admin.broadcast import router as broadcast_router
from routes.admin.revenue import router as revenue_router
from routes.admin.system import router as system_router

# Создаем главный роутер
from aiogram import Router

router = Router()

# Включаем все подроутеры
router.include_router(main_router)
router.include_router(statistics_router)
router.include_router(notifications_router)
router.include_router(user_management_router)
router.include_router(config_management_router)
router.include_router(broadcast_router)
router.include_router(revenue_router)
router.include_router(system_router)
