from __future__ import annotations

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
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from database import db
from models import models

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Константы и настройки
# ---------------------------------------------------------------------------

AUTH_CODE: str | None = os.getenv("AUTH_CODE")
COOKIE: str | None = os.getenv("COOKIE")

if AUTH_CODE is None:
    logger.warning("ENV AUTH_CODE is not set – all requests will be rejected")

if COOKIE is None:
    logger.warning("ENV COOKIE is not set – requests to panel may fail")

COUNTRY_SETTINGS: dict[str, dict[str, str]] = {
    "fi": {
        "urlcreate": "http://77.110.108.194:5580/hj0pGaxiL1U2cNG7bo/panel/inbound/addClient",
        "urlupdate": "http://77.110.108.194:5580/hj0pGaxiL1U2cNG7bo/panel/inbound/updateClient/",
        "urldelete": "http://77.110.108.194:5580/hj0pGaxiL1U2cNG7bo/panel/inbound/1/delClient/",
    },
    # "nl": {...}  # добавьте другие страны при необходимости
}

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Cookie": COOKIE or "",
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


async def panel_request(url: str, payload: Dict[str, Any] | None = None) -> httpx.Response:
    """Помощник для запросов к панели."""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            if payload is None:
                response = await client.post(url, headers=DEFAULT_HEADERS)
            else:
                response = await client.post(url, json=payload, headers=DEFAULT_HEADERS)
            return response
        except httpx.RequestError as exc:
            logger.error("HTTP request to %s failed: %s", url, exc)
            raise HTTPException(status_code=502, detail="Ошибка обращения к панели") from exc


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@router.post("/createconfig", response_model=List[str])
async def create_config(
    client_data: models.CreateData,
    _: None = Depends(verify_api_key),
) -> List[str]:
    """Создаёт `client_data.count` новых конфигураций и сохраняет их в БД."""

    created_ids: list[str] = []

    for _ in range(client_data.count):
        uid = str(uuid.uuid4())
        payload = build_payload(uid, enable=False)

        url = COUNTRY_SETTINGS[client_data.server]["urlcreate"]
        response = await panel_request(url, payload)

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
    _: None = Depends(verify_api_key),
) -> str:
    """Активирует свободную конфигурацию для пользователя."""

    expired_client = await db.get_one_expired_client(client_data.server)
    if not expired_client:
        raise HTTPException(
            status_code=409,
            detail="Свободных конфигов в данный момент нет, обратитесь в поддержку",
        )

    uid = expired_client[1]
    expiry_unix = int(time.time()) + (60 * 60 * 24 * client_data.time)

    payload = build_payload(uid, enable=True, expiry_time=expiry_unix)

    url = COUNTRY_SETTINGS[client_data.server]["urlupdate"] + uid
    response = await panel_request(url, payload)

    if response.status_code == 200:
        await db.update_user_code(
            tg_id=client_data.id,
            user_code=uid,
            time_end=expiry_unix,
            server_country=client_data.server,
        )
        logger.info("Config %s activated for tg_id %s", uid, client_data.id)
        return uid
    raise HTTPException(
        status_code=response.status_code,
        detail="Ошибка при обновлении конфигурации",
    )


@router.post("/extendconfig", response_model=str)
async def extend_config(
    update_data: models.ExtendConfig,
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
    response = await panel_request(url, payload)

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
    _: None = Depends(verify_api_key),
) -> str:
    """Удаляет конфигурацию по её `uid`."""

    uid = data.uid

    if await db.get_time_end_by_code(uid) is None:
        raise HTTPException(status_code=404, detail="Конфиг не найден или уже удалён")

    url = f"{COUNTRY_SETTINGS[data.server]['urldelete']}{uid}"
    response = await panel_request(url)

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
async def delete_all_configs(_: None = Depends(verify_api_key)) -> str:  # noqa: D401
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

        response = await panel_request(url)
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
    users = await db.get_codes_by_tg_id(tg_id)
    if not users:
        raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")

    result = [
        {"user_code": user_code, "time_end": time_end, "server": server}
        for user_code, time_end, server in users
    ]
    return JSONResponse(content=result)


@router.get("/subscription/{tg_id}")
async def get_subscription(tg_id: int):
    """Возвращает подписку из активных конфигов для V2rayTun в plain-text."""

    logger.info("Subscription request for tg_id: %s", tg_id)

    users = await db.get_codes_by_tg_id(tg_id)
    if not users:
        raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")

    current_time = int(time.time())
    active_configs: list[str] = []

    for user_code, time_end, server in users:
        if time_end > current_time:
            vless_config = (
                "vless://{user_code}@77.110.108.194:443?"
                "security=reality&encryption=none&pbk="
                "bMhOMGZho4aXhfoxyu7D9ZjVnM-02bR9dKBfIMMTVlc&"
                "headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&"
                "sni=google.com&sid=094e39c18a0e44#godnetvpn"
            ).format(user_code=user_code)
            active_configs.append(vless_config)

    if not active_configs:
        raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")

    subscription_content = "\n".join(active_configs)
    logger.info("Returning %s active configs for tg_id: %s", len(active_configs), tg_id)

    return PlainTextResponse(
        content=subscription_content,
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )


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
