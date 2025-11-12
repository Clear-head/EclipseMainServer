from typing import Optional, List
from pydantic import BaseModel



# 카테고리 상세 정보 DTO
class ReviewItemDTO(BaseModel):
    review_id: str
    category_id: str
    category_name: str
    category_type: Optional[str] = None
    comment: str
    stars: int
    created_at: str  # datetime을 문자열로 변환하여 전달
    nickname: Optional[str] = None


class RequestCategoryDetailDTO(BaseModel):
    category_id: str


class ResponseCategoryDetailDTO(BaseModel):
    id: str
    title: str
    image_url: str
    detail_address: str
    sub_category: str
    is_like: bool
    tags: Optional[List[str]]
    reviews: Optional[List[ReviewItemDTO]]
    average_stars: float = 0.0