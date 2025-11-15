from pydantic import BaseModel


# 계정 탈퇴

class RequestDeleteAccountDTO(BaseModel):
    password: str  # 본인 확인용 비밀번호
    because: str   # 탈퇴 사유