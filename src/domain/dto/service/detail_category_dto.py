from typing import Optional

from pydantic import BaseModel

from src.domain.dto.service.user_reivew_dto import UserReviewDTO


#   카드 선택 요청
class RequestDetailCategoryDTO(BaseModel):
    category_id: str


#   카드 선택 응답 본문
class ResponseDetailCategoryDTO(BaseModel):
    # average_stars: int
    id: str
    title: str
    image_url: str
    detail_address: str
    sub_category: str
    is_like: bool
    tags: Optional[list[str]]
    reviews: Optional[list[UserReviewDTO]]