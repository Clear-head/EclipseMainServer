from datetime import datetime

from pydantic import BaseModel, field_validator, ValidationError


class UserHistoryEntity(BaseModel):
    user_id: str
    visited_at: datetime
    category_id: str

    class Config:
        from_attributes = True

    @field_validator("user_id", "category_id")
    @classmethod
    def validate_null(cls, value):
        if value is None:
            raise ValidationError('[UserHistoryEntity] id is null')
        return value
