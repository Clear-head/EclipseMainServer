from pydantic import BaseModel


class ResponseDeleteAccount(BaseModel):
    user_id: str
    password: str