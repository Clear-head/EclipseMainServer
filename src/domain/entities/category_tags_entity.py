from typing import Optional

from pydantic import ValidationError, field_validator

from src.domain.dto.crawled.insert_category_tags_dto import InsertCategoryTagsDTO
from src.domain.entities.base_entity import BaseEntity


class CategoryTagsEntity(BaseEntity):
    id: Optional[int] = None
    tag_id: int
    category_id: str
    count: int

    @field_validator('tag_id')
    @classmethod
    def validate_null(cls, v):
        if v is None:
            raise ValidationError('[CategoryTagsEntity] any id is null')
        return v


    @classmethod
    def from_dto(cls, dto: InsertCategoryTagsDTO, id: int =None):
        return CategoryTagsEntity(
            id=id,
            **dto.model_dump()
        )