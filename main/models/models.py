from pydantic import BaseModel

class CreateData(BaseModel):
    """Данные для создания конфигураций.
    count — сколько новых конфигов создать (по умолчанию 1).
    """
    count: int = 1

class ExtendConfig(BaseModel):
    time: int
    uid: str  # id продлеваемого конфига

class ClientData(BaseModel):
    time: int
    id: str

class DeleteConfig(BaseModel):
    id: str

