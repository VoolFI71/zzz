from pydantic import BaseModel

class CreateData(BaseModel):
    """Данные для создания конфигураций.
    count — сколько новых конфигов создать (по умолчанию 1).
    server: код страны сервера (fi, nl).
    """
    count: int = 1
    server: str

class ExtendConfig(BaseModel):
    time: int
    uid: str  # id продлеваемого конфига

class ClientData(BaseModel):
    time: int
    id: str
    server: str

class DeleteConfig(BaseModel):
    uid: str  # id конфигурации для удаления

