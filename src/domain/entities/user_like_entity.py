from pydantic import field_validator

from src.domain.entities.base_entity import BaseEntity


class UserLikeEntity(BaseEntity):
    user_id: str
    category_id: str

    @field_validator('user_id', 'category_id')
    @classmethod
    def validate_null(cls, v):
        if v is None:
            raise ValueError('[UserLikeEntity] any id is null')
        return v