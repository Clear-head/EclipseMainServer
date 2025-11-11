from pydantic import BaseModel


class RequestDeleteAccount(BaseModel):
    password: str
    because: str