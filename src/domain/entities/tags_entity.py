from pydantic import field_validator, ValidationError

from src.domain.entities.base_entity import BaseEntity


class TagsEntity(BaseEntity):
    id: int
    name: str


    @field_validator("id")
    @classmethod
    def validate_id(cls, value):
        if not str(value).startswith(("1", "2", "3")):
            raise ValidationError("tag id error")
        else:
            return value