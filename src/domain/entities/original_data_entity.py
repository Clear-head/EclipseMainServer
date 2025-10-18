from datetime import datetime

from pydantic import field_validator, ValidationError

from src.domain.entities.base_entity import BaseEntity


class OriginalDataEntity(BaseEntity):
    id: str
    name: str
    address: str
    phone: str
    type: str
    image: str
    longitude: str
    latitude: str
    business_hour: str
    original_data: str
    last_crawl: datetime

    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        if v is None:
            raise ValidationError('id')
        return v

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, value: str) -> str:
        if len(value) > 11 or len(value) < 0:
            raise ValidationError('[OriginalDataEntity] longitude length error')
        else:
            try:
                tmp = float(value)
            except Exception:
                raise ValidationError('[OriginalDataEntity] longitude error')
        return value

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, value: str) -> str:
        if len(value) > 10 or len(value) < 0:
            raise ValidationError('[OriginalDataEntity] latitude length error')
        else:
            try:
                tmp = float(value)
            except Exception:
                raise ValidationError('[OriginalDataEntity] latitude error')
        return value