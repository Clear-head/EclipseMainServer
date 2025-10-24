from pydantic import BaseModel

from src.domain.dto.header import JsonHeader


#   로그인 실패 바디
class ErrorResponseBody(BaseModel):
    status_code: int
    message: str

class ErrorResponseDto(BaseModel):
    header: JsonHeader
    body: ErrorResponseBody