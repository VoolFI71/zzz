import os
import aiohttp
import logging

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
    """Возвращает True, если есть свободные конфиги. При указании `server` проверяется только эта страна."""
    url = "http://fastapi:8080/check-available-configs"
    if server is not None:
        url += f"?server={server}"
    headers = {"X-API-Key": AUTH_CODE}

    try:
        session = await get_session()
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("available", False)
            logger.warning("Unexpected status %s while checking configs", response.status)
    except Exception as exc:
        logger.error("Failed to check available configs: %s", exc)

    return False
