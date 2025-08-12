from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List

import httpx
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database import db
from fastapi import FastAPI
from models import models

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Константы и настройки
# ---------------------------------------------------------------------------

AUTH_CODE: str | None = os.getenv("AUTH_CODE")

if AUTH_CODE is None:
    logger.warning("ENV AUTH_CODE is not set – all requests will be rejected")

def _get_cookie(server_code: str) -> str:
    """Возвращает cookie для панели конкретного сервера.

    Ищет переменную окружения вида ``COOKIE_fi`` (регистр не важен).
    Если не найдено – вернёт пустую строку.
    """
    return os.getenv(f"COOKIE_{server_code.lower()}", "")

# Значения читаем из .env, чтобы не хранить в коде
def _env_any(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default

COUNTRY_SETTINGS: dict[str, dict[str, str]] = {
    "fi": {
        "urlcreate": _env_any("URLCREATE_FI", "urlcreate_fi", default=""),
        "urlupdate": _env_any("URLUPDATE_FI", "urlupdate_fi", default=""),
        "urldelete": _env_any("URLDELETE_FI", "urldelete_fi", default=""),
        # Параметры для генерации VLESS
        "host": _env_any("HOST_FI", "host_fi", default=""),
        "pbk": _env_any("PBK_FI", "pbk_fi", default=""),
        "sni": "google.com",
        "sid": _env_any("SID_FI", "sid_fi", default=""),
    },
    # "nl": {...}
}



router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def verify_api_key(x_api_key: str = Header(...)) -> None:  # noqa: D401
    """Проверяет корректность API-ключа.

    Используется как *dependency* во всех эндпоинтах.
    """
    if x_api_key != AUTH_CODE:
        raise HTTPException(status_code=403, detail="Нет доступа")


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def build_payload(uid: str, enable: bool, expiry_time: int = 0) -> Dict[str, Any]:
    """Формирует payload для панели управления."""
    return {
        "id": 1,
        "settings": json.dumps(
            {
                "clients": [
                    {
                        "id": uid,
                        "flow": "xtls-rprx-vision",
                        "email": str(random.randint(10_000_000, 100_000_000)),
                        "limitIp": 1,
                        "totalGB": 0,
                        "expiryTime": expiry_time * 1000 if expiry_time else 0,
                        "enable": enable,
                        "tgId": "",
                        "subId": str(random.randint(10_000_000, 100_000_000)),
                        "comment": "",
                        "reset": 0,
                    }
                ]
            }
        ),
    }


async def panel_request(request: Request, url: str, server_code: str, payload: Dict[str, Any] | None = None) -> httpx.Response:
    """Помощник для запросов к панели."""
    headers = {
        "Content-Type": "application/json",
        "Cookie": _get_cookie(server_code),
    }
    # Берём общий клиент из app.state
    async def _do_request(client: httpx.AsyncClient) -> httpx.Response:
        if payload is None:
            return await client.post(url, headers=headers)
        return await client.post(url, json=payload, headers=headers)

    # Ретраи на сетевые ошибки
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            # Получаем клиента из request.app.state
            http_client = getattr(request.app.state, "http_client", None)
            if http_client is not None:
                return await _do_request(http_client)
            # Fallback: локальный клиент (не должно часто срабатывать)
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as tmp_client:
                return await _do_request(tmp_client)
        except httpx.RequestError as exc:
            last_exc = exc
            await asyncio.sleep(0.3 * (attempt + 1))
    logger.error("HTTP request to %s failed after retries: %s", url, last_exc)
    raise HTTPException(status_code=502, detail="Ошибка обращения к панели")


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@router.post("/createconfig", response_model=List[str])
async def create_config(
    client_data: models.CreateData,
    request: Request,
    _: None = Depends(verify_api_key),
) -> List[str]:
    """Создаёт `client_data.count` новых конфигураций и сохраняет их в БД."""

    created_ids: list[str] = []

    for _ in range(client_data.count):
        uid = str(uuid.uuid4())
        payload = build_payload(uid, enable=False)

        url = COUNTRY_SETTINGS[client_data.server]["urlcreate"]
        response = await panel_request(request, url, client_data.server, payload)

        if response.status_code == 200:
            await db.insert_into_db(
                tg_id=None,
                user_code=uid,
                time_end=0,
                server_country=client_data.server,
            )
            created_ids.append(uid)
            logger.info("Config %s created", uid)
        else:
            logger.error(
                "Failed to create config, status=%s, body=%s",
                response.status_code,
                response.text,
            )
            raise HTTPException(
                status_code=response.status_code,
                detail="Ошибка при создании конфигурации",
            )

    return created_ids


@router.post("/giveconfig", response_model=str)
async def give_config(
    client_data: models.ClientData,
    request: Request,
    _: None = Depends(verify_api_key),
) -> str:
    """Активирует свободную конфигурацию для пользователя с атомарной бронью."""

    # 1) Пытаемся зарезервировать свободный конфиг атомарно
    reserved_uid = await db.reserve_one_free_config(
        reserver_tg_id=str(client_data.id),
        server_country=client_data.server,
        reservation_ttl_seconds=120,
    )
    if not reserved_uid:
        raise HTTPException(
            status_code=409,
            detail="Свободных конфигов в данный момент нет, обратитесь в поддержку",
        )

    expiry_unix = int(time.time()) + (60 * 60 * 24 * client_data.time)
    payload = build_payload(reserved_uid, enable=True, expiry_time=expiry_unix)
    url = COUNTRY_SETTINGS[client_data.server]["urlupdate"] + reserved_uid

    # 2) Обновляем конфиг на панели
    response = await panel_request(request, url, client_data.server, payload)

    if response.status_code != 200:
        # Откатываем бронь, чтобы конфиг снова стал доступен
        try:
            await db.cancel_reserved_config(reserved_uid, str(client_data.id))
        finally:
            pass
        raise HTTPException(
            status_code=response.status_code,
            detail="Ошибка при обновлении конфигурации на панели",
        )

    # 3) Финализируем бронь в БД
    finalized = await db.finalize_reserved_config(
        user_code=reserved_uid,
        reserver_tg_id=str(client_data.id),
        final_time_end=expiry_unix,
        server_country=client_data.server,
    )
    if finalized == 0:
        # Маловероятный случай: бронь истекла или потеряна; пробуем отменить на панели невозможно здесь
        # Возвращаем ошибку, просим поддержку
        logger.error(
            "Finalization failed for uid %s (tg_id %s, server %s) after panel success",
            reserved_uid,
            client_data.id,
            client_data.server,
        )
        # Попробуем снять бронь на всякий случай
        try:
            await db.cancel_reserved_config(reserved_uid, str(client_data.id))
        finally:
            pass
        raise HTTPException(status_code=500, detail="Ошибка финализации. Обратитесь в поддержку.")

    logger.info(
        "Config %s activated for tg_id %s on server %s",
        reserved_uid,
        client_data.id,
        client_data.server,
    )
    return reserved_uid


@router.post("/extendconfig", response_model=str)
async def extend_config(
    update_data: models.ExtendConfig,
    request: Request,
    _: None = Depends(verify_api_key),
) -> str:
    """Продлевает срок действия конфига на `update_data.time` суток."""

    uid = update_data.uid
    added_seconds = update_data.time * 60 * 60 * 24

    current_time_end = await db.get_time_end_by_code(uid)
    if current_time_end is None:
        raise HTTPException(status_code=404, detail="Конфигурация не найдена")

    base_time = max(current_time_end, int(time.time()))
    new_time_end = base_time + added_seconds

    payload = build_payload(uid, enable=True, expiry_time=new_time_end)

    url = f"{COUNTRY_SETTINGS[update_data.server]['urlupdate']}{uid}"
    response = await panel_request(request, url, update_data.server, payload)

    if response.status_code == 200:
        await db.set_time_end(uid, new_time_end)
        logger.info("Config %s extended till %s (unix)", uid, new_time_end)
        return "Конфиг успешно продлён"
    raise HTTPException(
        status_code=response.status_code,
        detail="Ошибка при продлении конфигурации",
    )


@router.delete("/deleteconfig", response_model=str)
async def delete_config(
    data: models.DeleteConfig,
    request: Request,
    _: None = Depends(verify_api_key),
) -> str:
    """Удаляет конфигурацию по её `uid`."""

    uid = data.uid

    if await db.get_time_end_by_code(uid) is None:
        raise HTTPException(status_code=404, detail="Конфиг не найден или уже удалён")

    url = f"{COUNTRY_SETTINGS[data.server]['urldelete']}{uid}"
    response = await panel_request(request, url, data.server)

    if response.status_code != 200:
        logger.error(
            "Failed to delete config %s on panel: %s / %s",
            uid,
            response.status_code,
            response.text,
        )
        raise HTTPException(
            status_code=response.status_code,
            detail="Ошибка при удалении конфигурации на панели",
        )

    rows = await db.delete_user_code(uid)
    if rows == 0:
        raise HTTPException(status_code=404, detail="Конфиг не найден в БД")

    logger.info("Config %s deleted", uid)
    return "Конфиг успешно удалён"


# ---------------------------------------------------------------------------
# Сервисные эндпоинты
# ---------------------------------------------------------------------------

@router.delete("/delete-all-configs", response_model=str)
async def delete_all_configs(request: Request, _: None = Depends(verify_api_key)) -> str:  # noqa: D401
    """Удаляет все конфиги: сначала на панели, затем в БД."""
    rows = await db.get_all_user_codes()
    if not rows:
        return "Нет конфигов для удаления"

    deleted, failed = 0, 0
    for uid, server in rows:
        # 1. Пытаемся удалить конфиг на панели управления
        try:
            url = f"{COUNTRY_SETTINGS[server]['urldelete']}{uid}"
        except KeyError:
            logger.error("Unknown server country %s for uid %s", server, uid)
            failed += 1
            continue

        response = await panel_request(request, url, server)
        if response.status_code == 200:
            # 2. Удаляем запись из БД
            await db.delete_user_code(uid)
            deleted += 1
        else:
            logger.error(
                "Failed to delete config %s on panel: %s / %s",
                uid,
                response.status_code,
                response.text,
            )
            failed += 1

    logger.info("Bulk delete done: success=%s, failed=%s", deleted, failed)
    return f"Удалено {deleted} конфигураций, ошибок {failed}"

@router.get("/check-available-configs")
async def check_available_configs(
    server: str | None = Query(
        default=None, description="Код страны сервера, например `fi`"),
    _: None = Depends(verify_api_key),
):
    """Проверяет наличие свободных конфигов."""

    # Сначала сбрасываем истёкшие конфиги, чтобы отразить актуальную доступность
    try:
        await db.reset_expired_configs()
    except Exception:
        pass
    
    available_config = await db.get_one_expired_client(server)
    return JSONResponse(
        content={
            "available": bool(available_config),
            "message": (
                "Свободные конфиги доступны"
                if available_config
                else "Свободных конфигов в данный момент нет"
            ),
        }
    )

@router.get("/usercodes/{tg_id}")
async def read_user(tg_id: int, _: None = Depends(verify_api_key)):
    # Сначала сбрасываем истёкшие конфиги
    #await db.reset_expired_configs()
    
    users = await db.get_codes_by_tg_id(tg_id)
    if not users:
        raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")

    result = [
        {"user_code": user_code, "time_end": time_end, "server": server}
        for user_code, time_end, server in users
    ]
    return JSONResponse(content=result)

# @router.get("/subscription/{tg_id}")
# async def get_subscription(tg_id: int):
#     """Возвращает подписку из активных конфигов для V2rayTun в plain-text."""

#     logger.info("Subscription request for tg_id: %s", tg_id)

#     # Сначала сбрасываем истёкшие конфиги
#     #await db.reset_expired_configs()

#     users = await db.get_codes_by_tg_id(tg_id)
#     if not users:
#         raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")

#     current_time = int(time.time())
#     active_configs: list[str] = []

#     for user_code, time_end, server in users:
#         if time_end > current_time:
#             settings = COUNTRY_SETTINGS.get(server)
#             if not settings:
#                 # Если сервер неизвестен – пропускаем
#                 logger.warning("Unknown server %s for user_code %s", server, user_code)
#                 continue
#             vless_config = (
#                 f"vless://{user_code}@{settings['host']}:443?"
#                 f"security=reality&encryption=none&pbk={settings['pbk']}&"
#                 f"headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&"
#                 f"sni={settings['sni']}&sid={settings['sid']}#glsvpn"
#             )
#             active_configs.append(vless_config)

#     if not active_configs:
#         raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")

#     subscription_content = "\n".join(active_configs)
#     logger.info("Returning %s active configs for tg_id: %s", len(active_configs), tg_id)

#     return PlainTextResponse(
#         content=subscription_content,
#         headers={"Content-Type": "text/plain; charset=utf-8"},
#     )

@router.get("/add-config", response_class=HTMLResponse)
async def add_config_page(
    request: Request,
    config: str | None = None,
    expiry: int | None = None,
):
    """Веб-страница для добавления конфига в V2rayTun."""

    return templates.TemplateResponse(
        "add_config.html",
        {"request": request, "config": config, "expiry": expiry},
    )

@router.get("/redirect")
async def add_config_redirect(
    config: str = Query(..., description="Строка конфигурации или base64(config) для импорта в V2rayTun"),
):
    """Редиректит на схему v2raytun://import/{base64(config)}.

    Поддерживает как сырой VLESS-текст, так и уже закодированный base64.
    """
    raw_config: str
    # Пробуем распознать base64 → если удачно и похоже на vless, используем его
    try:
        decoded = base64.b64decode(config, validate=True).decode()
        if decoded.startswith(("vless://", "vmess://", "trojan://")):
            raw_config = decoded
        else:
            raw_config = config
    except Exception:
        raw_config = config

    encoded_config = base64.b64encode(raw_config.encode()).decode()
    return RedirectResponse(url=f"v2raytun://import/{encoded_config}", status_code=307)


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):  # noqa: D401
    """Красочная посадочная страница VPN."""
    return templates.TemplateResponse("index.html", {"request": request})
