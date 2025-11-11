from datetime import datetime

from pydantic import BaseModel, field_validator, ValidationError


class ReviewsEntity(BaseModel):
    id: str
    user_id: str
    category_id: str
    stars: int
    comments: str
    created_at: datetime

    @field_validator('id', 'user_id', 'category_id')
    @classmethod
    def validate_null(cls, v):
        if v is None:
            raise ValidationError('[ReviewEntity] null exception')
        return v


    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v):
        if v is None:
            v = datetime.now()
        return v

    @field_validator("stars")
    @classmethod
    def validate_stars(cls, value: int) -> int:
        if value < 0 or value > 5:
            raise ValidationError("[ReviewEntity] stars error")
        return value