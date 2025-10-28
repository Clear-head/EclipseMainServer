from pydantic import BaseModel

from src.domain.dto.header import JsonHeader


class RequestAccessTokenBody(BaseModel):
    token: str


class RequestAccessTokenDto(BaseModel):
    headers: JsonHeader
    body: RequestAccessTokenBody


class ResponseAccessTokenBody(BaseModel):
    headers: JsonHeader
    body: RequestAccessTokenBody