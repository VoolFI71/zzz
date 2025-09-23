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
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
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
    "nl": {
        "urlcreate": _env_any("URLCREATE_NL", "urlcreate_nl", default=""),
        "urlupdate": _env_any("URLUPDATE_NL", "urlupdate_nl", default=""),
        "urldelete": _env_any("URLDELETE_NL", "urldelete_nl", default=""),
        # Параметры для генерации VLESS
        "host": _env_any("HOST_NL", "host_nl", default="146.103.102.21"),
        "pbk": _env_any("PBK_NL", "pbk_nl", default=""),
        "sni": "google.com",
        "sid": _env_any("SID_NL", "sid_nl", default=""),
    },
    "fi": {
        "urlcreate": _env_any("URLCREATE_FI", "urlcreate_fi", default=""),
        "urlupdate": _env_any("URLUPDATE_FI", "urlupdate_fi", default=""),
        "urldelete": _env_any("URLDELETE_FI", "urldelete_fi", default=""),
        # Параметры для генерации VLESS
        "host": _env_any("HOST_FI", "host_fi", default="77.110.108.194"),
        "pbk": _env_any("PBK_FI", "pbk_fi", default=""),
        "sni": "www.vk.com",
        "sid": _env_any("SID_FI", "sid_fi", default=""),
    },
}

COUNTRY_LABELS: dict[str, str] = {
    "nl": "Netherlands 🇳🇱",
    "fi": "Finland 🇫🇮",
}

def _is_browser_request(headers: dict[str, str]) -> bool:
    """Грубая эвристика определения браузера для контент-nega.

    Возвращает True для браузеров (отдаём HTML), False для клиентов/приложений (отдаём text/plain).
    """
    ua = headers.get("user-agent", "").lower()
    accept = headers.get("accept", "").lower()
    # Современные браузеры отправляют Sec-Fetch-* и/или ch-ua заголовки
    has_sec_fetch = any(h in headers for h in ("sec-fetch-mode", "sec-fetch-site", "sec-ch-ua"))
    if has_sec_fetch:
        return True
    # Явно HTML в Accept → браузер
    if "text/html" in accept:
        return True
    # По User-Agent
    browser_markers = ("mozilla", "chrome", "safari", "firefox", "edg/")
    if any(marker in ua for marker in browser_markers):
        return True
    return False


router = APIRouter()
templates = Jinja2Templates(directory="templates")
BASE_URL: str = os.getenv("BASE_URL", "https://swaga.space")

# Subscription response metadata (v2RayTun headers)
SUB_TITLE: str = _env_any("SUBSCRIPTION_TITLE", "sub_title", default="GLS VPN")
SUB_UPDATE_HOURS: str = _env_any("SUBSCRIPTION_UPDATE_HOURS", "sub_update_hours", default="12")
SUB_ANNOUNCE: str = _env_any("SUBSCRIPTION_ANNOUNCE", "sub_announce", default="")
SUB_ANNOUNCE_URL: str = _env_any("SUBSCRIPTION_ANNOUNCE_URL", "sub_announce_url", default="")
SUB_ROUTING_B64: str = _env_any("SUBSCRIPTION_ROUTING_B64", "sub_routing_b64", default="")

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

@router.post(
    "/createconfig",
    response_model=List[str],
)
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
        logger.info("panel.create URL=%s", url)
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


@router.post(
    "/giveconfig",
    response_model=str,
)
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
    logger.info("panel.update URL=%s", url)

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
    # Ensure a permanent subscription key is created for this user (idempotent)
    try:
        await db.get_or_create_sub_key(str(client_data.id))
    except Exception:
        pass
    return reserved_uid


@router.post(
    "/extendconfig",
    response_model=str,
)
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
    logger.info("panel.extend URL=%s", url)
    response = await panel_request(request, url, update_data.server, payload)

    if response.status_code == 200:
        await db.set_time_end(uid, new_time_end)
        logger.info("Config %s extended till %s (unix)", uid, new_time_end)
        return "Конфиг успешно продлён"
    raise HTTPException(
        status_code=response.status_code,
        detail="Ошибка при продлении конфигурации",
    )


@router.delete(
    "/deleteconfig",
    response_model=str,
)
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
    logger.info("panel.delete URL=%s", url)
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

@router.delete(
    "/delete-all-configs",
    response_model=str,
)
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

@router.get(
    "/check-available-configs",
)
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

@router.get(
    "/usercodes/{tg_id}",
)
async def read_user(tg_id: int, _: None = Depends(verify_api_key)):
    # Сначала сбрасываем истёкшие конфиги
    #await db.reset_expired_configs()
    try:
        await db.get_or_create_sub_key(str(tg_id))
    except Exception:
        pass
    users = await db.get_codes_by_tg_id(tg_id)
    if not users:
        raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")

    result = [
        {"user_code": user_code, "time_end": time_end, "server": server}
        for user_code, time_end, server in users
    ]
    return JSONResponse(content=result)


async def get_subscription(tg_id: int):
    """Возвращает подписку из активных конфигов для V2rayTun.

    Добавляет заголовки (как HTTP, так и в теле) совместимые с v2RayTun:
    - profile-title
    - subscription-userinfo (expire=...)
    - profile-update-interval (часы)
    - routing (base64), announce, announce-url — если заданы в env
    """

    logger.info("Subscription request for tg_id: %s", tg_id)

    users = await db.get_codes_by_tg_id(tg_id)
    if not users:
        raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")

    current_time = int(time.time())
    active_configs: list[str] = []
    max_expire_unix: int = 0

    for user_code, time_end, server in users:
        if time_end > current_time:
            settings = COUNTRY_SETTINGS.get(server)
            if not settings:
                # Если сервер неизвестен – пропускаем
                logger.warning("Unknown server %s for user_code %s", server, user_code)
                continue
            label = COUNTRY_LABELS.get(server, "SHARD VPN")
            vless_config = (
                f"vless://{user_code}@{settings['host']}:443?"
                f"security=reality&encryption=none&pbk={settings['pbk']}&"
                f"headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&"
                f"sni={settings['sni']}&sid={settings['sid']}#{label}"
            )
            active_configs.append(vless_config)
            if time_end > max_expire_unix:
                max_expire_unix = time_end

    if not active_configs:
        raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")

    # Compose optional body headers for compatibility
    body_header_lines: list[str] = []
    if SUB_TITLE:
        body_header_lines.append(f'profile-title: "{SUB_TITLE}"')
    if max_expire_unix > 0:
        body_header_lines.append(f'subscription-userinfo: "expire={max_expire_unix}"')
    if SUB_UPDATE_HOURS:
        body_header_lines.append(f'profile-update-interval: "{SUB_UPDATE_HOURS}"')
    if SUB_ROUTING_B64:
        body_header_lines.append(f'routing: "{SUB_ROUTING_B64}"')
    if SUB_ANNOUNCE:
        body_header_lines.append(f'announce: "{SUB_ANNOUNCE}"')
    if SUB_ANNOUNCE_URL:
        body_header_lines.append(f'announce-url: "{SUB_ANNOUNCE_URL}"')

    subscription_content = ("\n".join(body_header_lines + [""]) if body_header_lines else "") + "\n".join(active_configs)
    logger.info("Returning %s active configs for tg_id: %s (expire=%s)", len(active_configs), tg_id, max_expire_unix)

    # Also include headers at HTTP level
    response_headers: dict[str, str] = {"Content-Type": "text/plain; charset=utf-8"}
    if SUB_TITLE:
        response_headers["profile-title"] = SUB_TITLE
    if max_expire_unix > 0:
        response_headers["subscription-userinfo"] = f"expire={max_expire_unix}"
    if SUB_UPDATE_HOURS:
        response_headers["profile-update-interval"] = SUB_UPDATE_HOURS
    if SUB_ROUTING_B64:
        response_headers["routing"] = SUB_ROUTING_B64
    if SUB_ANNOUNCE:
        response_headers["announce"] = SUB_ANNOUNCE
    if SUB_ANNOUNCE_URL:
        response_headers["announce-url"] = SUB_ANNOUNCE_URL

    return PlainTextResponse(
        content=subscription_content,
        headers=response_headers,
    )

@router.get("/subscription/{sub_key}", response_class=HTMLResponse)
async def add_config_page(
    request: Request,
    config: str | None = None,
    expiry: int | None = None,
    sub_key: str | None = None,
    subscription: str | None = None,
):
    # Контент-нега: если это не браузер — отдаём plain text (для импорта в V2rayTun)
    if not _is_browser_request({k.lower(): v for k, v in request.headers.items()}):
        # 1) Если передан subscription=..., отдадим его как есть
        if subscription:
            return PlainTextResponse(content=subscription)
        # 2) Если передан sub_key, разворачиваем его в tg_id и возвращаем подписку
        if sub_key is not None:
            tg_id_str = await db.get_tg_id_by_key(sub_key)
            if tg_id_str is None:
                raise HTTPException(status_code=404, detail="subscription key not found")
            sub_resp = await get_subscription(int(tg_id_str))  # reuse существующей логики
            return PlainTextResponse(content=sub_resp.body.decode("utf-8"), headers=dict(sub_resp.headers))
        # 3) Если пришёл config (vless/vmess/trojan), отдадим его как текст
        if config:
            try:
                # Если пришёл base64 — проверим и декодируем
                decoded = base64.b64decode(config, validate=True).decode()
                if decoded.startswith(("vless://", "vmess://", "trojan://")):
                    return PlainTextResponse(content=decoded)
            except Exception:
                pass
            # Иначе считаем, что это уже сырой конфиг
            return PlainTextResponse(content=config)
        # Нечего отдавать
        return PlainTextResponse(content="", status_code=204)
    # Иначе рендерим HTML-страницу для пользователя
    return templates.TemplateResponse(
        "subscription.html",
        {"request": request, "config": config, "expiry": expiry, "sub_key": sub_key, "subscription": subscription},
    )

@router.get("/sub/{user_id}")
async def get_sub_key(user_id: str, _: None = Depends(verify_api_key)):
    try:
        sub_key = await db.get_or_create_sub_key(str(user_id))
    except Exception:
        raise HTTPException(status_code=500, detail="Ошибка. Попробуйте позже.")
    return JSONResponse({"sub_key": sub_key})




@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):  # noqa: D401
    """Красочная посадочная страница VPN."""
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------------------
# SEO: robots.txt и sitemap.xml
# ---------------------------------------------------------------------------

@router.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )
    return PlainTextResponse(content=content, media_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    urls: list[str] = [
        f"{BASE_URL}/",
        f"{BASE_URL}/subscription",
    ]
    urlset = "\n".join(
        f"  <url>\n    <loc>{loc}</loc>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>" for loc in urls
    )
    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        f"{urlset}\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")
