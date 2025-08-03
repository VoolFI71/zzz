from pydantic import BaseModel

class CreateData(BaseModel):
    auth: str

class ClientData(BaseModel):
    auth: str
    time: int 
    id: str

class AuthData(BaseModel):
    auth: str