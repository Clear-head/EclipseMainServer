from pydantic import BaseModel, field_validator


class UserLikeEntity(BaseModel):
    user_id: str
    category_id: str

    class Config:
        from_attributes = True

    @field_validator('user_id', 'category_id')
    @classmethod
    def validate_null(cls, v):
        if v is None:
            raise ValueError('[UserLikeEntity] any id is null')
        return v