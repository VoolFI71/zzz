from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import json
import uuid
import random
import requests
import time
from fastapi.responses import JSONResponse
import os
import aiosqlite

app = FastAPI()

urlcreate = "http://77.110.108.194:5580/hj0pGaxiL1U2cNG7bo/panel/inbound/addClient"
urlupdate = "http://77.110.108.194:5580/hj0pGaxiL1U2cNG7bo/panel/inbound/updateClient/"

headers = {
    "Content-Type": "application/json",
    "Cookie": os.getenv("COOKIE")
}

async def init_db():
    async with aiosqlite.connect("users.db") as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id TEXT,
                user_code TEXT, 
                time_end INTEGER
            )
        ''')
        await conn.commit()

async def insert_into_db(tg_id, user_code, time_end):
    async with aiosqlite.connect("users.db") as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            INSERT INTO users (tg_id, user_code, time_end) VALUES (?, ?, ?)
        ''', (tg_id, user_code, time_end))
        await conn.commit()

async def get_one_expired_client():
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            current_time = int(time.time())
            
            await cursor.execute('''
                SELECT * FROM users WHERE time_end = 0 OR time_end < ?
                LIMIT 1
            ''', (current_time,))
            
            expired_client = await cursor.fetchone()
    
    return expired_client

async def update_user_code(tg_id: str, user_code: str, time_end: int):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('''
                UPDATE users
                SET tg_id = ?, time_end = ?
                WHERE user_code = ?
            ''', (tg_id, time_end, user_code))
            
            await conn.commit() 
            
            updated_rows = cursor.rowcount
    
    return updated_rows

class CreateData(BaseModel):
    auth: str

class ClientData(BaseModel):
    auth: str
    time: int 
    id: str

@app.post("/createconfig", response_model=str)
async def create_config(client_data: CreateData):
    await init_db()
    if client_data.auth != '+7999999999999999999':
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
        await insert_into_db(tg_id=None, user_code=id, time_end=0)
        return "Конфигурация создана успешно"
    else:
        raise HTTPException(status_code=response.status_code, detail="Ошибка при создании конфигурации")

@app.post("/giveconfig", response_model=str)
async def create_config(client_data: ClientData):
    if client_data.auth != '+7999999999999999999':
        raise HTTPException(status_code=403, detail="Нет доступа")
        
    uid = await get_one_expired_client()
    if uid:
        uid = uid[1]
    else:
        raise HTTPException(status_code=409, detail="Свободных конфигов в данный момент нет, обратитесь в поддержку")

    exptime = (int(time.time()) + (60 * 60 * 24 * 31 * client_data.time))
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
        await update_user_code(tg_id=client_data.id, user_code=uid, time_end=exptime)
        print("Конфигурация успешно обновлена и готова к работа")
        return str(uid)
    else:
        raise HTTPException(status_code=response.status_code, detail="Ошибка при обновлении конфигурации")

async def get_codes_by_tg_id(tg_id):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT user_code, time_end FROM users WHERE tg_id = ?', (tg_id,))
            rows = await cursor.fetchall() 
    
    return rows

@app.get("/usercodes/{tg_id}")
async def read_user(tg_id: int):
    users = await get_codes_by_tg_id(tg_id)
    if not users:
        raise HTTPException(status_code=404, detail="Конфигурации не найдены")
    
    result = [{"user_code": user[0], "time_end": user[1]} for user in users]
    return JSONResponse(content=result)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080) 