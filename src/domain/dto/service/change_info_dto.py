from pydantic import BaseModel


class RequestChangeInfoDto(BaseModel):
    user_id: str
    change_field: str
    password: str


class ResponseChangeInfoDto(BaseModel):
    msg: str