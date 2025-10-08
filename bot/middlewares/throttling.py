from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Deque, Dict, Hashable, Optional, Tuple

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import CallbackQuery, Message


class ThrottlingMiddleware(BaseMiddleware):
    """
    Simple per-user, per-handler throttling middleware for Aiogram v3.

    Controls frequency of invoking handlers on a sliding time window basis.

    Flags supported on handlers (via @router.message(..., flags={...})):
      - throttle_key: str            # logical key for grouping; defaults to handler function name
      - throttle_window: float       # seconds, default = self.default_window
      - throttle_burst: int          # allowed events per window, default = self.default_burst
      - throttle_exempt: bool        # bypass throttling for this handler

    You can also globally exempt specific user IDs via allowlist_user_ids.
    """

    def __init__(
        self,
        default_window: float = 1.5,
        default_burst: int = 3,
        allowlist_user_ids: Optional[set[int]] = None,
    ) -> None:
        super().__init__()
        self.default_window = max(0.1, float(default_window))
        self.default_burst = max(1, int(default_burst))
        self.allowlist_user_ids = allowlist_user_ids or set()
        # key: (user_id, throttle_key) -> deque[timestamps]
        self._buckets: Dict[Tuple[int, Hashable], Deque[float]] = {}
        # Protect the buckets mapping in concurrent environment
        self._lock = asyncio.Lock()

    async def __call__(self, handler, event, data):  # type: ignore[override]
        user_id = self._extract_user_id(event)
        # If we can't identify a user, just proceed
        if user_id is None or user_id in self.allowlist_user_ids:
            return await handler(event, data)

        # Read flags set on the handler
        if get_flag(data, "throttle_exempt") is True:
            return await handler(event, data)

        throttle_key = self._resolve_key(handler, data)
        window = float(get_flag(data, "throttle_window") or self.default_window)
        burst = int(get_flag(data, "throttle_burst") or self.default_burst)

        now = time.monotonic()
        key = (user_id, throttle_key)

        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket

            # Drop events outside of window
            cutoff = now - window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            # If we already reached burst within window -> throttle
            if len(bucket) >= burst:
                await self._notify_throttled(event, window)
                return  # swallow the event

            # Record current event timestamp and proceed
            bucket.append(now)

        return await handler(event, data)

    @staticmethod
    def _extract_user_id(event) -> Optional[int]:
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        # Fallbacks (just in case other update types are used later)
        user = getattr(event, "from_user", None)
        return getattr(user, "id", None)

    @staticmethod
    def _resolve_key(handler, data) -> Hashable:
        # Explicit key via flags has priority
        explicit = get_flag(data, "throttle_key")
        if explicit is not None:
            return explicit
        # Otherwise, use underlying callback function name (per-handler)
        callback = getattr(handler, "callback", None)
        if callback is not None:
            return getattr(callback, "__name__", str(callback))
        return "__unknown_handler__"

    @staticmethod
    async def _notify_throttled(event, window: float) -> None:
        try:
            if isinstance(event, CallbackQuery):
                await event.answer(f"Слишком часто. Подождите {window:.1f} сек.", show_alert=False)
            elif isinstance(event, Message):
                await event.answer(f"Слишком часто. Повторите через {window:.1f} сек.")
        except Exception:
            # Swallow any notification errors silently
            pass


