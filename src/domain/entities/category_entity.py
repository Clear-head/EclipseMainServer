from pydantic import BaseModel, field_validator, ValidationError


class CategoryEntity(BaseModel):
    id: str
    tags: str

    class Config:
        from_attributes = True

    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        if v is None:
            raise ValidationError('[CategoryEntity] id is null')
        return v