from datetime import datetime

from pydantic import field_validator, ValidationError

from src.domain.entities.base_entity import BaseEntity


class UserHistoryEntity(BaseEntity):
    id: str
    user_id: str
    visited_at: datetime
    cafe: str
    restaurant: str
    contents: str
    template: str

    @field_validator("user_id", "visited_at")
    @classmethod
    def validate_null(cls, value):
        if value is None:
            raise ValidationError('[UserHistoryEntity] null exception')
        return value
