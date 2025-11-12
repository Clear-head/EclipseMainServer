from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


# 리뷰 작성/수정 DTO

class RequestCreateReviewDTO(BaseModel):
    category_id: str
    stars: int
    comments: str


class RequestUpdateReviewDTO(BaseModel):
    review_id: str
    stars: int
    comments: str


class ResponseDeleteReviewDTO(BaseModel):
    message: str = "삭제되었습니다"
    review_id: str


# 리뷰 조회 DTO

class ReviewDTO(BaseModel):
    review_id: str
    category_id: str
    category_name: str
    category_type: Optional[str] = None
    comment: str
    stars: int
    created_at: datetime
    nickname: Optional[str] = None


class ResponseReviewListDTO(BaseModel):
    review_list: Optional[List[ReviewDTO]] = []


class ResponseReviewCountDTO(BaseModel):
    review_count: int