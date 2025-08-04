import os
import aiohttp
import logging

AUTH_CODE = os.getenv("AUTH_CODE")

logger = logging.getLogger(__name__)

async def check_available_configs() -> bool:
    """Запрашивает FastAPI-сервис и возвращает True, если есть свободные конфиги."""
    url = "http://fastapi:8080/check-available-configs"
    headers = {"X-API-Key": AUTH_CODE}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("available", False)
                logger.warning("Unexpected status %s while checking configs", response.status)
    except Exception as exc:
        logger.error("Failed to check available configs: %s", exc)

    return False
