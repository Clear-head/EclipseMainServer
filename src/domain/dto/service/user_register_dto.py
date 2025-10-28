from typing import Optional

from pydantic import BaseModel
from datetime import datetime
from src.domain.dto.header import JsonHeader


#   회원가입 요청시 바디
class RequestRegisterBody(BaseModel):
    id: str
    username: str
    password: str
    nickname: str
    birth: Optional[datetime] = None
    phone: Optional[str] = None
    email: str
    sex: Optional[int] = None
    address: Optional[str] = None


#   화원가입 요청 틀
class RequestRegisterDto(BaseModel):
    header: JsonHeader
    body: RequestRegisterBody


class ResponseRegisterBody(BaseModel):
    status_code: int
    message: str

class ResponseRegisterDto(BaseModel):
    header: JsonHeader
    body: ResponseRegisterBody