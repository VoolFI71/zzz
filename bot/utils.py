import os
import aiohttp
import logging
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Iterable

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

SERVER_DISPLAY_NAMES: dict[str, str] = {
    "fi": "🇫🇮 Финляндия",
    "ge": "🇩🇪 Германия",
    "nl": "🇳🇱 Нидерланды",
    "us": "🇺🇸 США",
    "pl": "🇵🇱 Польша",
    "se": "🇸🇪 Швеция",
    "fr": "🇫🇷 Франция",
    "gb": "🇬🇧 Великобритания",
    "uk": "🇬🇧 Великобритания",
    "tr": "🇹🇷 Турция",
}


def format_server_name(code: str) -> str:
    """Возвращает красивое имя сервера с флагом."""

    return SERVER_DISPLAY_NAMES.get(code.lower(), code.upper())


def format_server_list(server_codes: Iterable[str]) -> str:
    """Собирает человекочитаемый список серверов для сообщений."""

    seen: list[str] = []
    for code in server_codes:
        label = format_server_name(code)
        if label not in seen:
            seen.append(label)
    return ", ".join(seen) if seen else "—"

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
    - Иначе читаем из ENV SERVER_ORDER (например, "ge"), иначе дефолт ["ge"].
    """
    if preferred_order is None:
        env_order = os.getenv("SERVER_ORDER", "ge")
        preferred_order = [s.strip().lower() for s in env_order.split(",") if s.strip()]
        if not preferred_order:
            preferred_order = ["ge"]

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


def _parse_server_order() -> list[str]:
    env_order = os.getenv("SERVER_ORDER", "ge")
    order = [s.strip().lower() for s in env_order.split(",") if s.strip()]
    return order or ["ge"]


def _get_region_variants_map() -> dict[str, list[str]]:
    """Возвращает карту базового кода региона -> список вариантов серверов.

    Читает переменные окружения вида SERVER_VARIANTS_FI, SERVER_VARIANTS_GE.
    Если переменная не задана, по умолчанию использует один вариант — сам базовый код.
    """
    region_to_variants: dict[str, list[str]] = {}
    for base in _parse_server_order():
        env_key = f"SERVER_VARIANTS_{base.upper()}"
        raw = os.getenv(env_key, base)
        variants = [s.strip().lower() for s in raw.split(",") if s.strip()]
        # уникализируем порядок
        seen: set[str] = set()
        uniq: list[str] = []
        for v in variants:
            if v not in seen:
                uniq.append(v)
                seen.add(v)
        region_to_variants[base] = uniq or [base]
    return region_to_variants


async def pick_servers_one_per_region(order_bases: list[str] | None = None) -> list[str]:
    """Выбирает по одному серверу из каждой региональной группы (ge*).

    Стратегия: для каждой базовой страны берём первый вариант, на котором есть свободные конфиги
    (по данным /check-available-configs?server=...). Если ни один вариант не доступен,
    возвращаем первый из списка (best-effort), чтобы не блокировать логику — окончательная
    проверка произойдёт на /giveconfig.
    """
    bases = order_bases or _parse_server_order()
    region_map = _get_region_variants_map()
    picked: list[str] = []
    for base in bases:
        variants = region_map.get(base, [base])
        chosen: str | None = None
        for code in variants:
            try:
                if await check_available_configs(code):
                    chosen = code
                    break
            except Exception:
                # переходим к следующему варианту
                continue
        picked.append(chosen or variants[0])
    return picked


async def check_all_servers_available() -> bool:
    """Проверяет доступность по регионам: для каждой базовой страны (из SERVER_ORDER)
    должен быть доступен хотя бы один вариант (ge/ge2...).

    Если у региона нет ни одного доступного варианта — возвращает False.
    """
    region_map = _get_region_variants_map()
    logger.info(f"Checking availability by regions: {region_map}")
    for base, variants in region_map.items():
        region_ok = False
        for code in variants:
            try:
                if await check_available_configs(code):
                    region_ok = True
                    break
            except Exception as e:
                logger.warning(f"Error checking server {code}: {e}")
                continue
        if not region_ok:
            logger.warning(f"No available servers found for region {base} among {variants}")
            return False
    logger.info("All regions have at least one available server")
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

