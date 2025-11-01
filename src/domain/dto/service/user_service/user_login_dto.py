from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


#   유저가 로그인 시에 보내는 요청
class GetUserLoginDto(BaseModel):
    id: str
    password: str


class AfterLoginUserInfo(BaseModel):
    username: str
    nickname: str
    birth: Optional[datetime] = None
    phone: Optional[str] = None
    email: EmailStr
    address: Optional[str] = None


#   로그인 로직 이후 유저에게 보내는 응답
class ToUserLoginDto(BaseModel):
    message: str
    token1: str
    token2: str
    info: AfterLoginUserInfo

