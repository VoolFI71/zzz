from pydantic import BaseModel

class ExtendConfig(BaseModel):
    time: int
    uid: str #id продлеваемого конфига

class ClientData(BaseModel):
    time: int
    id: str

