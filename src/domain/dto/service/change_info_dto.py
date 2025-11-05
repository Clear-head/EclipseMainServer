from pydantic import BaseModel


class RequestChangeInfoDto(BaseModel):
    change_field: str
    password: str


class ResponseChangeInfoDto(BaseModel):
    msg: str