"""
Profile module - разбит на подмодули для лучшей организации кода.

Структура:
- main.py - основные функции профиля
- trial.py - пробная подписка
- configs.py - управление конфигами
- balance.py - управление балансом
- callbacks.py - callback обработчики
"""

from .main import router as main_router
from .trial import router as trial_router
from .configs import router as configs_router
from .balance import router as balance_router
from .callbacks import router as callbacks_router

# Объединяем все роутеры
from aiogram import Router

router = Router()
router.include_router(main_router)
router.include_router(trial_router)
router.include_router(configs_router)
router.include_router(balance_router)
router.include_router(callbacks_router)
