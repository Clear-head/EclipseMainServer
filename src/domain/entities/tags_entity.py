from pydantic import field_validator, ValidationError
from src.domain.entities.base_entity import BaseEntity


class TagsEntity(BaseEntity):
    id: int
    name: str


    @field_validator("id")
    def validate_id(self, value):
        if not str(value).startswith(("10", "20", "30")):
            raise ValidationError("tag id error")