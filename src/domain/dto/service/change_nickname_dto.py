from pydantic import BaseModel


class RequestChangeNicknameDto(BaseModel):
    user_id: str
    nickname: str


class ResponseChangeNicknameDto(BaseModel):
    msg: str