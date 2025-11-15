from pydantic import BaseModel, ConfigDict


# 크롤링 태그 삽입 DTO
class InsertCrawledTagsDTO(BaseModel):
    tag_id: int
    category_id: str
    count: int

    model_config = ConfigDict(from_attributes=True)