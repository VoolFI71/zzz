from pydantic import BaseModel

class CreateData(BaseModel):
    pass

class ClientData(BaseModel):
    time: int
    id: str

class AuthData(BaseModel):
    auth: str