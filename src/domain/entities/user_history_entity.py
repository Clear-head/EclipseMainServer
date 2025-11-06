from datetime import datetime
from typing import Optional

from pydantic import field_validator, ValidationError

from src.domain.entities.base_entity import BaseEntity
from src.utils.uuid_maker import generate_uuid


class UserHistoryEntity(BaseEntity):
    id: str
    merge_id: str
    seq: int
    user_id: str
    visited_at: datetime
    category_id: str
    category_name: str
    duration: Optional[int]               #   초단위
    transportation: Optional[str]
    description: Optional[str]


    @field_validator("user_id", "visited_at")
    @classmethod
    def validate_null(cls, value):
        if value is None:
            raise ValidationError('[UserHistoryEntity] null exception')
        return value

    @classmethod
    def from_dto(cls, user_id, merge_id, order, category_id, category_name, transportation, duration=None, visited_at=None, id=None, description=None):
        return cls(
            id=id if id is not None else generate_uuid(),
            user_id=user_id,
            merge_id=merge_id,
            seq=order,
            category_id=category_id,
            category_name=category_name,
            duration=duration,
            transportation=transportation,
            visited_at=datetime.now(),
            description=description
        )