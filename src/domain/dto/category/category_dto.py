from typing import List, Optional

from pydantic import BaseModel



# 메인 화면 카테고리 리스트 DTO
class CategoryListItemDTO(BaseModel):
    id: str
    title: str
    image_url: str
    detail_address: str
    sub_category: str
    lat: Optional[str] = None
    lng: Optional[str] = None
    review_count: int = 0
    average_stars: float = 0.0


class ResponseCategoryListDTO(BaseModel):
    categories: List[CategoryListItemDTO]