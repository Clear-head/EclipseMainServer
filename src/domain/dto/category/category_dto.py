from typing import List, Optional

from pydantic import BaseModel, field_validator


# 메인 화면 카테고리 리스트 DTO
class CategoryListItemDTO(BaseModel):
    id: str
    title: str
    image_url: str
    detail_address: str
    sub_category: str
    lat: Optional[str] = None
    lng: Optional[str] = None
    type: Optional[int] = None
    review_count: int = 0
    average_stars: float = 0.0


    @field_validator("average_stars", mode="before")
    @classmethod
    def validate_avg_stars(cls, v):
        if v is None:
            return 0.0
        return float(round(v, 2))



class ResponseCategoryListDTO(BaseModel):
    categories: List[CategoryListItemDTO]