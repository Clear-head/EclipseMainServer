from typing import Optional

from pydantic import BaseModel
from datetime import datetime
from src.domain.dto.header import JsonHeader


#   회원가입 요청시 바디
class RequestRegisterBody(BaseModel):
    id: str
    password: str
    nickname: str
    email: str
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    sex: Optional[int] = None
    birth: Optional[datetime] = None


#   화원가입 요청 틀
class RequestRegisterDto(BaseModel):
    header: JsonHeader
    body: RequestRegisterBody