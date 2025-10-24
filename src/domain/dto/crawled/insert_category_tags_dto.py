from pydantic import BaseModel, ConfigDict


class InsertCategoryTagsDTO(BaseModel):
    tag_id: int
    category_id: str
    count: int

    model_config = ConfigDict(from_attributes=True)