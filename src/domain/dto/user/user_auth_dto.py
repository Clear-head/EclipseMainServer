from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from src.domain.entities.base_entity import BaseEntity


# 로그인

class RequestLoginDTO(BaseModel):
    id: str
    password: str


class UserInfoDTO(BaseModel):
    username: str
    nickname: str
    birth: Optional[datetime] = None
    phone: Optional[str] = None
    email: EmailStr
    address: Optional[str] = None


class ResponseLoginDTO(BaseModel):
    message: str
    token1: str  # Access Token
    token2: str  # Refresh Token
    info: UserInfoDTO


# 회원가입

class RequestRegisterDTO(BaseEntity):
    id: str
    username: str
    password: str
    nickname: str
    birth: Optional[datetime] = None
    phone: Optional[str] = None
    email: str
    sex: Optional[int] = None
    address: Optional[str] = None


class ResponseRegisterDTO(BaseModel):
    message: str


# 토큰

class RequestRefreshTokenDTO(BaseModel):
    token: str
    id: str