from datetime import datetime

from src.domain.entities.base_entity import BaseEntity


class BlackEntity(BaseEntity):
    id: int
    user_id: str
    phone: str
    email: str
    sanction: str
    period: datetime
    started_at: datetime