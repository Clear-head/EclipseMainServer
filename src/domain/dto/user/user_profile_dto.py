from pydantic import BaseModel


# 프로필 수정

class RequestUpdateProfileDTO(BaseModel):
    change_field: str  # 변경할 값
    password: str      # 본인 확인용 비밀번호


class ResponseUpdateProfileDTO(BaseModel):
    msg: str