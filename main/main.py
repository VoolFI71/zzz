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
from routers import routers
from database import db
app = FastAPI()
app.include_router(routers.router)

async def start_application():
    await db.init_db()  # Инициализация базы данных при запуске приложения

@app.on_event("startup")
async def startup_event():
    await start_application()  # Инициализация базы данных при старте приложения

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)