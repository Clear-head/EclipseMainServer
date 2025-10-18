from pydantic import field_validator, ValidationError
from src.domain.entities.base_entity import BaseEntity


class CategoryEntity(BaseEntity):
    id: str
    tags: str

    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        if v is None:
            raise ValidationError('[CategoryEntity] id is null')
        return v