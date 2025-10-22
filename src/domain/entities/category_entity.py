from datetime import datetime
from pydantic import field_validator, ValidationError
from src.domain.dto.insert_category_dto import InsertCategoryDto
from src.domain.entities.base_entity import BaseEntity
from src.utils.uuid_maker import generate_uuid

class CategoryEntity(BaseEntity):
    id: str
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
            return ValueError('[CategoryEntity] 휴대폰 번호 검증 에러')
        return v


    @classmethod
    def from_dto(cls, dto: InsertCategoryDto):
        return cls(
            id = generate_uuid(),
            **dto.model_dump(),
            last_crawl=datetime.now()
        )
