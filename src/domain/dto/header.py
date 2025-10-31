from typing import Optional

from pydantic import BaseModel


class JsonHeader(BaseModel):
    content_type: str = "application/json"
    jwt: Optional[str] = None