import os
import aiohttp
import logging
import asyncio
import time
from contextlib import asynccontextmanager

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


# --- Server selection helpers ---

async def pick_first_available_server(preferred_order: list[str] | None = None) -> str | None:
    """Возвращает первый сервер из списка, на котором есть свободные конфиги.

    Порядок:
    - Если передан preferred_order — используем его.
    - Иначе читаем из ENV SERVER_ORDER (например, "fi,ge"), иначе дефолт ["fi", "ge"].
    """
    if preferred_order is None:
        env_order = os.getenv("SERVER_ORDER", "fi,ge")
        preferred_order = [s.strip().lower() for s in env_order.split(",") if s.strip()]
        if not preferred_order:
            preferred_order = ["fi", "ge"]

    # Уникализируем, сохраняем порядок
    seen: set[str] = set()
    order: list[str] = []
    for s in preferred_order:
        if s and s not in seen:
            order.append(s)
            seen.add(s)

    for server in order:
        try:
            if await check_available_configs(server):
                return server
        except Exception:
            # Переходим к следующему серверу
            continue
    return None


async def check_all_servers_available() -> bool:
    """Проверяет, что ВСЕ основные серверы (Германия и Финляндия) доступны.
    
    Возвращает True только если ВСЕ серверы fi и ge доступны.
    Если хотя бы один сервер недоступен, возвращает False.
    """
    # Получаем список серверов из конфигурации
    env_order = os.getenv("SERVER_ORDER", "fi,ge")
    servers_to_check = [s.strip().lower() for s in env_order.split(",") if s.strip()]
    if not servers_to_check:
        servers_to_check = ["fi", "ge"]
    
    logger.info(f"Checking availability of all servers: {servers_to_check}")
    
    for server in servers_to_check:
        try:
            if not await check_available_configs(server):
                logger.warning(f"Server {server} is NOT available")
                return False
        except Exception as e:
            logger.warning(f"Error checking server {server}: {e}")
            return False
    
    logger.info(f"All servers {servers_to_check} are available")
    return True

# --- Simple per-user rate limiting and action locks ---

_last_action_at: dict[tuple[int | str, str], float] = {}
_action_locks: dict[tuple[int | str, str], asyncio.Lock] = {}

def _now() -> float:
    return time.monotonic()

def should_throttle(user_id: int | str, action_key: str, cooldown_seconds: float) -> tuple[bool, float]:
    """Returns (throttled, retry_after_seconds).

    - If called more than once within cooldown_seconds for same (user_id, action_key), it throttles.
    - Records the attempt timestamp when allowed.
    """
    key = (user_id, action_key)
    last_at = _last_action_at.get(key, 0.0)
    now_ts = _now()
    elapsed = now_ts - last_at
    if elapsed < cooldown_seconds:
        return True, cooldown_seconds - elapsed
    _last_action_at[key] = now_ts
    return False, 0.0

@asynccontextmanager
async def acquire_action_lock(user_id: int | str, action_key: str):
    """Serialize concurrent executions for the same (user, action)."""
    key = (user_id, action_key)
    lock = _action_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _action_locks[key] = lock
    await lock.acquire()
    try:
        yield
    finally:
        lock.release()

