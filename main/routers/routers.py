import json
import random
import uuid
import time
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import aiosqlite
from pydantic import BaseModel
from fastapi import APIRouter
from database import db
from models import models
import os
import logging
logger = logging.getLogger(__name__)
from fastapi import Depends, Header

AUTH_CODE = os.getenv("AUTH_CODE")
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# urlcreate = "http://89.111.142.122:5580/yCovzGorXa84wzvrpX/panel/inbound/addClient"
# urlupdate = "http://89.111.142.122:5580/yCovzGorXa84wzvrpX/panel/inbound/updateClient/"

urlcreate = "http://77.110.108.194:5580/hj0pGaxiL1U2cNG7bo/panel/inbound/addClient"
urlupdate = "http://77.110.108.194:5580/hj0pGaxiL1U2cNG7bo/panel/inbound/updateClient/"

headers = {
    "Content-Type": "application/json",
    "Cookie": os.getenv("COOKIE")
}

@router.post("/createconfig", response_model=list[str])
async def create_config(client_data: models.CreateData, x_api_key: str = Header(...)):
    """
    Создаёт `client_data.count` новых конфигураций и сохраняет их в базе.
    Возвращает список созданных `uid`.
    """
    logger.info("/createconfig called, count=%s", client_data.count)
    if x_api_key != AUTH_CODE:
        raise HTTPException(status_code=403, detail="Нет доступа")

    created_ids: list[str] = []

    for _ in range(client_data.count):
        uid = str(uuid.uuid4())
        payload = {
            "id": 1,
            "settings": json.dumps({
                "clients": [{
                    "id": uid,
                    "flow": "xtls-rprx-vision",
                    "email": str(random.randint(10_000_000, 100_000_000)),
                    "limitIp": 1,
                    "totalGB": 0,
                    "expiryTime": 0,
                    "enable": False,
                    "tgId": "",
                    "subId": str(random.randint(10_000_000, 100_000_000)),
                    "comment": "",
                    "reset": 0
                }]
            })
        }

        response = requests.post(urlcreate, json=payload, headers=headers)
        if response.status_code == 200:
            await db.insert_into_db(tg_id=None, user_code=uid, time_end=0)
            created_ids.append(uid)
            logger.info("Config %s created", uid)
        else:
            logger.error("Failed to create config, status=%s, body=%s", response.status_code, response.text)
            raise HTTPException(status_code=response.status_code, detail="Ошибка при создании конфигурации")

    return created_ids

@router.post("/giveconfig", response_model=str)
async def give_config(client_data: models.ClientData, x_api_key: str = Header(...)):
    if x_api_key != AUTH_CODE:
        raise HTTPException(status_code=403, detail="Нет доступа")
        
    uid = await db.get_one_expired_client()
    if uid:
        uid = uid[1]
    else:
        raise HTTPException(status_code=409, detail="Свободных конфигов в данный момент нет, обратитесь в поддержку")

    exptime = (int(time.time()) + (60 * 60 * 24 * client_data.time))
    data = {
        "id": 1,
        "settings": json.dumps({
            "clients": [{
                "id": uid,
                "flow": "xtls-rprx-vision",
                "email": str(random.randint(10000000, 100000000)),
                "limitIp": 1,
                "totalGB": 0,
                "expiryTime": exptime * 1000,
                "enable": True,
                "tgId": "",
                "subId": str(random.randint(10000000, 100000000)),
                "comment": "",
                "reset": 0
            }]
        })
    }  

    response = requests.post(urlupdate+str(uid), json=data, headers=headers)
    if response.status_code == 200:
        await db.update_user_code(tg_id=client_data.id, user_code=uid, time_end=exptime)
        logger.info("Config %s activated for tg_id %s", uid, client_data.id)
        return str(uid)
    else:
        raise HTTPException(status_code=response.status_code, detail="Ошибка при обновлении конфигурации")

@router.post("/extendconfig", response_model=str)
async def extend_config(update_data: models.ExtendConfig, x_api_key: str = Header(...)):
    """
    Продлевает срок действия конфига на `update_data.time` суток. При продлении время
    добавляется к текущему `time_end`, а не перезаписывает его.
    """
    if x_api_key != AUTH_CODE:
        raise HTTPException(status_code=403, detail="Нет доступа")

    uid = update_data.uid
    added_seconds = update_data.time * 60 * 60 * 24

    # Текущее значение time_end из базы
    current_time_end = await db.get_time_end_by_code(uid)
    if current_time_end is None:
        raise HTTPException(status_code=404, detail="Конфигурация не найдена")

    # Если конфиг уже истёк, начинаем отсчёт от текущего времени
    base_time = max(current_time_end, int(time.time()))
    new_time_end = base_time + added_seconds

    data = {
        "id": 1,
        "settings": json.dumps({
            "clients": [{
                "id": uid,
                "flow": "xtls-rprx-vision",
                "email": str(random.randint(10_000_000, 100_000_000)),
                "limitIp": 1,
                "totalGB": 0,
                "expiryTime": new_time_end * 1000,  # миллисекунды
                "enable": True,
                "tgId": "",
                "subId": str(random.randint(10_000_000, 100_000_000)),
                "comment": "",
                "reset": 0
            }]
        })
    }

    response = requests.post(f"{urlupdate}{uid}", json=data, headers=headers)
    if response.status_code == 200:
        await db.set_time_end(uid, new_time_end)  # сохраняем новое время окончания
        logger.info("Config %s extended till %s (unix)", uid, new_time_end)
        return "Конфиг успешно продлён"
    else:
        raise HTTPException(status_code=response.status_code, detail="Ошибка при продлении конфигурации")

@router.get("/check-available-configs")
async def check_available_configs(x_api_key: str = Header(...)):
    if x_api_key != AUTH_CODE:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    # Проверяем наличие свободных конфигов
    available_config = await db.get_one_expired_client()
    
    if available_config:
        return JSONResponse(content={"available": True, "message": "Свободные конфиги доступны"})
    else:
        return JSONResponse(content={"available": False, "message": "Свободных конфигов в данный момент нет"})

@router.get("/usercodes/{tg_id}")
async def read_user(tg_id: int, x_api_key: str = Header(...)):
    if x_api_key != AUTH_CODE:
        raise HTTPException(status_code=403, detail="Нет доступа")

    users = await db.get_codes_by_tg_id(tg_id)
    if not users:
        raise HTTPException(status_code=404, detail="У вас нет актвных конфигураций")
    
    result = [{"user_code": user[0], "time_end": user[1]} for user in users]
    return JSONResponse(content=result)

@router.get("/subscription/{tg_id}")
async def get_subscription(tg_id: int):
    """
    Возвращает подписку с конфигами пользователя для V2rayTun
    Формат: plain text с VLESS-ссылками, разделенными переносами строк
    """
    logger.info(f"Subscription request for tg_id: {tg_id}")
    
    users = await db.get_codes_by_tg_id(tg_id)
    logger.info(f"Found users data: {users}")
    
    if not users:
        logger.warning(f"No configurations found for tg_id: {tg_id}")
        raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")
    
    # Фильтруем только активные конфиги
    current_time = int(time.time())
    active_configs = []
    
    for user_code, time_end in users:
        if time_end > current_time:  # Конфиг еще активен
            vless_config = (
                f"vless://{user_code}@77.110.108.194:443?"
                "security=reality&encryption=none&pbk=bMhOMGZho4aXhfoxyu7D9ZjVnM-02bR9dKBfIMMTVlc&"
                "headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&sni=google.com&sid=094e39c18a0e44#godnetvpn"
            )
            active_configs.append(vless_config)
    
    if not active_configs:
        raise HTTPException(status_code=404, detail="У вас нет активных конфигураций")
    
    # Возвращаем конфиги как plain text, разделенные переносами строк
    subscription_content = "\n".join(active_configs)
    logger.info(f"Returning {len(active_configs)} active configs for tg_id: {tg_id}")
    
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=subscription_content,
        headers={
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

@router.get("/add-config", response_class=HTMLResponse)
async def add_config_page(request: Request, config: str = None, expiry: int = None):
    """
    Веб-страница для добавления конфига в V2rayTun
    """
    return templates.TemplateResponse("add_config.html", {
        "request": request,
        "config": config,
        "expiry": expiry
    })