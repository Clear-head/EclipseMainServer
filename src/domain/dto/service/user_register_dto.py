from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.domain.entities.base_entity import BaseEntity


#   회원가입 요청
class RequestRegisterDto(BaseEntity):
    id: str
    username: str
    password: str
    nickname: str
    birth: Optional[datetime] = None
    phone: Optional[str] = None
    email: str
    sex: Optional[int] = None
    address: Optional[str] = None


class ResponseRegisterDto(BaseModel):
    message: str
