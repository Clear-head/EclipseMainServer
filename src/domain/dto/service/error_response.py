from pydantic import BaseModel

from src.domain.dto.header import JsonHeader

class ErrorResponseBody(BaseModel):
    status_code: int
    message: str

class ErrorResponseDto(BaseModel):
    header: JsonHeader
    body: ErrorResponseBody