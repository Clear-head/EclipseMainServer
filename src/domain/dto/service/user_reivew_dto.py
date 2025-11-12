"""

    내 리뷰 목록 요청 응답

"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class UserReviewDTO(BaseModel):
    review_id: str
    category_id: str
    category_name: str
    category_type: Optional[str] = None
    comment: str
    stars: int
    created_at: datetime
    nickname: Optional[str] = None


class ResponseUserReviewDTO(BaseModel):
    review_list: Optional[List[UserReviewDTO]] = []