# Пустой файл для создания пакета

# Импортируем функцию is_admin из main модуля
try:
    from .main import is_admin
    __all__ = ['is_admin']
except ImportError:
    # Если импорт не удался, создаем заглушку
    def is_admin(user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором."""
        return user_id == 746560409
    
    __all__ = ['is_admin']

# Создаем router и импортируем все подроутеры
from aiogram import Router

router = Router()

# Импортируем все роутеры из модулей
try:
    from .main import router as main_router
    from .statistics import router as statistics_router
    from .notifications import router as notifications_router
    from .user_management import router as user_management_router
    from .config_management import router as config_management_router
    from .broadcast import router as broadcast_router
    from .revenue import router as revenue_router
    from .system import router as system_router
    
    # Включаем все подроутеры
    router.include_router(main_router)
    router.include_router(statistics_router)
    router.include_router(notifications_router)
    router.include_router(user_management_router)
    router.include_router(config_management_router)
    router.include_router(broadcast_router)
    router.include_router(revenue_router)
    router.include_router(system_router)
except ImportError as e:
    print(f"Warning: Could not import admin modules: {e}")

# Добавляем router в __all__
__all__.append('router')
