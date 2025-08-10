

from __future__ import annotations

from aiogram import Router

from callback.handlers.common import common_router
from callback.handlers.stars import stars_router
from callback.handlers.yookassa import yookassa_router

callback_router = Router()
callback_router.include_router(common_router)
callback_router.include_router(stars_router)
callback_router.include_router(yookassa_router)

