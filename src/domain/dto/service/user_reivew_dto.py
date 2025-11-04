"""

    내 리뷰 목록 요청 응답

"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

class RequestGetUserReviewDTO(BaseModel):
    user_id: str


class RequestSetUserReviewDTO(BaseModel):
    user_id: str
    history_id: str
    stars: int
    comment: str
    visited_at: datetime
    created_at: datetime


class UserReviewDTO(BaseModel):
    review_id: str
    category_id: str
    category_name: str
    comment: str
    stars: int
    created_at: datetime

class ResponseUserReviewDTO(BaseModel):
    review_list: Optional[List[UserReviewDTO]] = []