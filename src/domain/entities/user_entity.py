from pydantic import field_validator, EmailStr
import datetime
from src.domain.entities.base_entity import BaseEntity

"""

    id, nickname -> 한글 최대 85 자리지만 커뮤니케이션 서버 제작 후 다시 설정

"""


class UserEntity(BaseEntity):
    id: str
    username: str
    password: str
    nickname: str
    birth: datetime.datetime
    phone: str
    email: EmailStr
    sex: bool
    address: str

    @field_validator('id', "password", "username", "nickname", "email")
    @classmethod
    def validate_id(cls, v):
        if v is None:
            raise ValueError('[UserEntity] null exception')
        return v

    @field_validator('phone')
    @classmethod
    def check_password(cls, value):
        if len(value) > 12 or len(value) < 9:
            return ValueError('[UserEntity] 휴대폰 번호 검증 에러')
        return value
