from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RequestUserSanctionsDTO(BaseModel):
    user_id: str
    user_email: Optional[str]
    user_phone: Optional[str]
    sanctions: Optional[str]
    finished_at: datetime