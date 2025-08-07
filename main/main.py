from fastapi import FastAPI
import uvicorn

from database import db  # noqa: WPS412
from routers import routers

app = FastAPI()
app.include_router(routers.router)


@app.on_event("startup")
async def startup_event() -> None:
    """Инициализируем БД при запуске приложения."""
    await db.init_db()


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Проверка работоспособности приложения для Docker."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
