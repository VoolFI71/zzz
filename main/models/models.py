from pydantic import BaseModel

class CreateData(BaseModel):
    """Пустая модель-заглушка для /createconfig (тело запроса не используется)."""
    pass

class ExtendConfig(BaseModel):
    time: int
    uid: str  # id продлеваемого конфига

class ClientData(BaseModel):
    time: int
    id: str

