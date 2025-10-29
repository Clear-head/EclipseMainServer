from pydantic import BaseModel


class RequestAccessTokenDto(BaseModel):
    token: str
    id : str

