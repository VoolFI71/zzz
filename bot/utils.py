import os
import aiohttp
import logging
import asyncio

_session: aiohttp.ClientSession | None = None

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=15)
        connector = aiohttp.TCPConnector(limit=100, ssl=False)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    return _session

AUTH_CODE = os.getenv("AUTH_CODE")

logger = logging.getLogger(__name__)

async def check_available_configs(server: str | None = None) -> bool:
    """Возвращает True, если есть свободные конфиги.

    Поведение:
    - 200: читаем флаг available из ответа
    - 401/403 и любые иные коды ответа: считаем, что свободных нет (False)
    - Сетевые ошибки/таймаут: не блокируем оплату (True), окончательная проверка произойдёт в /giveconfig
    """
    base_url = "http://fastapi:8080"
    url = f"{base_url}/check-available-configs"
    if server is not None:
        url += f"?server={server}"
    headers = {"X-API-Key": AUTH_CODE} if AUTH_CODE else {}

    try:
        session = await get_session()
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("available", False)
            # Любой не-200 считаем как отсутствие свободных конфигов
            logger.warning("/check-available-configs returned %s", response.status)
            return False
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.error("Network error while checking configs: %s", exc)
        return True
    except Exception as exc:
        logger.error("Unexpected error while checking configs: %s", exc)
        return False

