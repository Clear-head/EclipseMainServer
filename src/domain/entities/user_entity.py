from pydantic import BaseModel, field_validator, EmailStr
import datetime

"""

    id, nickname -> 한글 최대 85 자리지만 커뮤니케이션 서버 제작 후 다시 설정

"""


class UserEntity(BaseModel):
    id: str
    username: str
    password: str
    nickname: str
    birth: datetime.datetime
    phone: str
    email: EmailStr
    sex: bool
    address: str

    class Config:
        from_attributes = True

    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        if v is None:
            raise ValueError('[UserEntity] id is null')
        return v

    @field_validator('phone')
    @classmethod
    def check_password(cls, value):
        if len(value) > 11:
            return ValueError('[UserEntity] 휴대폰 번호 검증 에러')
        return value
