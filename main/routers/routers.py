import json
import random
import uuid
import time
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
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

urlcreate = "http://77.110.108.194:5580/hj0pGaxiL1U2cNG7bo/panel/inbound/addClient"
urlupdate = "http://77.110.108.194:5580/hj0pGaxiL1U2cNG7bo/panel/inbound/updateClient/"

headers = {
    "Content-Type": "application/json",
    "Cookie": os.getenv("COOKIE")
}

@router.post("/createconfig", response_model=str)
async def create_config(client_data: models.CreateData, x_api_key: str = Header(...)):
    logger.info("/createconfig called")
    if x_api_key != AUTH_CODE:
        raise HTTPException(status_code=403, detail="Нет доступа")

    id = str(uuid.uuid4())
    data = {
        "id": 1,
        "settings": json.dumps({
            "clients": [{
                "id": id,
                "flow": "xtls-rprx-vision",
                "email": str(random.randint(1000000, 10000000)),
                "limitIp": 1,
                "totalGB": 0,
                "expiryTime": 0,
                "enable": False,
                "tgId": "",
                "subId": str(random.randint(1000000, 10000000)),
                "comment": "",
                "reset": 0
            }]
        })
    }

    response = requests.post(urlcreate, json=data, headers=headers)
    if response.status_code == 200:
        await db.insert_into_db(tg_id=None, user_code=id, time_end=0)
        return "Конфигурация создана успешно"
    else:
        raise HTTPException(status_code=response.status_code, detail="Ошибка при создании конфигурации")

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
                "email": str(random.randint(1000000, 10000000)),
                "limitIp": 1,
                "totalGB": 0,
                "expiryTime": exptime * 1000,
                "enable": True,
                "tgId": "",
                "subId": str(random.randint(1000000, 10000000)),
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