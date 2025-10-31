from datetime import datetime
from typing import Optional

from pydantic import field_validator, ValidationError

from src.domain.dto.crawled.insert_category_dto import InsertCategoryDto
from src.domain.entities.base_entity import BaseEntity
from src.utils.uuid_maker import generate_uuid


class CategoryEntity(BaseEntity):
    id: str = generate_uuid()
    name: str
    do: str
    si: str
    gu: str
    detail_address: str
    sub_category: str
    business_hour: str
    phone: str
    type: int
    image: str
    latitude: str
    longitude: str
    menu: Optional[str]
    last_crawl: datetime


    @field_validator('id', "type", "latitude", "longitude", "last_crawl")
    @classmethod
    def validate_id(cls, v):
        if v is None:
            raise ValidationError('[CategoryEntity] null exception')
        return v


    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if len(v) > 12 or len(v) < 9:
            return ""
        return v


    @classmethod
    def from_dto(cls, dto: InsertCategoryDto, id: str = None):
        return cls(
            id = id if id is not None else generate_uuid(),
            **dto.model_dump(),
            last_crawl=datetime.now()
        )