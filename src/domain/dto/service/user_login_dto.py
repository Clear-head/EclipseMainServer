from pydantic import BaseModel
from src.domain.dto.header import JsonHeader


#   유저가 로그인 시에 보내는 요청 바디
class GetUserLoginBody(BaseModel):
    id: str
    password: str


#   로그인 로직 이후 유저에게 보내는 응답 바디
class ToUserLoginBody(BaseModel):
    status_code: int
    message: str
    token1: str
    token2: str


#   유저가 로그인 시에 보내는 요청 json 틀
class GetUserLoginDto(BaseModel):
    headers: JsonHeader
    body: GetUserLoginBody


#   유저에게 로그인 시에 보내는 응답 바디
class ToUserLoginDto(BaseModel):
    headers: JsonHeader
    body: ToUserLoginBody

