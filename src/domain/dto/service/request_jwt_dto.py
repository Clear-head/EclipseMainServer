from pydantic import BaseModel

from src.domain.dto.header import JsonHeader


class RequestAccessTokenBody(BaseModel):
    access_token: str


class RequestAccessTokenDto(BaseModel):
    header: JsonHeader
    body: RequestAccessTokenBody