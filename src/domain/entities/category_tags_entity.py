from pydantic import ValidationError, field_validator
from sqlalchemy import Column

from src.domain.entities.base_entity import BaseEntity


class CategoryTagsEntity(BaseEntity):
    id: int
    tag_id: int
    category_id: str
    count: int

    @field_validator('tag_id')
    @classmethod
    def validate_null(cls, v):
        if v is None:
            raise ValidationError('[ReviewEntity] any id is null')
        return v