from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
import uvicorn
import httpx
import asyncio
import os
import logging

from database import db  # noqa: WPS412
from routers import routers

# Rate limiting

app = FastAPI()
app.include_router(routers.router)

# Простой аудит-лог запросов (middleware должен регистрироваться до старта приложения)
logger = logging.getLogger("audit")

@app.middleware("http")
async def audit_log(request: Request, call_next):
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "-")
    api_key = request.headers.get("x-api-key", "-")
    path = request.url.path
    method = request.method
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as exc:
        logger.exception("request_error method=%s path=%s ip=%s", method, path, client_ip)
        raise exc
    logger.info("request method=%s path=%s status=%s ip=%s api_key_present=%s", method, path, status, client_ip, bool(api_key))
    return response


@app.on_event("startup")
async def startup_event() -> None:
    """Инициализируем БД при запуске приложения."""
    await db.init_db()
    # Глобальный HTTP-клиент для реюза соединений к панели
    timeout = httpx.Timeout(15.0, connect=5.0)
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    app.state.http_client = httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    )

    # Rate limiter отключён — Redis не используется

    # Опциональная фоновая чистка истёкших конфигов
    enable_sweep = os.getenv("ENABLE_EXPIRE_SWEEP", "true").lower() in {"1", "true", "yes"}
    sweep_interval = int(os.getenv("EXPIRE_SWEEP_SECONDS", "300"))

    async def _expire_sweeper() -> None:
        while True:
            try:
                await db.reset_expired_configs()
            except Exception:
                # Не падаем из-за фоновой задачи
                logger.exception("Background sweeper task failed")
            await asyncio.sleep(sweep_interval)

    app.state.expire_task = None
    if enable_sweep:
        app.state.expire_task = asyncio.create_task(_expire_sweeper())

    # Монтируем статику (CSS/JS/изображения)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")



@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Проверка работоспособности приложения для Docker."""
    return {"status": "ok"}


@app.on_event("shutdown")
async def shutdown_event() -> None:
    client = getattr(app.state, "http_client", None)
    if client is not None:
        await client.aclose()
    task = getattr(app.state, "expire_task", None)
    if task is not None:
        task.cancel()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
