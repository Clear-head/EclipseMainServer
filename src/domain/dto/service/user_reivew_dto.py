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
    category_type: str # 내가 쓴 리뷰에서 타입 가져오려고, my_review_screen에 필요
    comment: str
    stars: int
    created_at: datetime


class ResponseUserReviewDTO(BaseModel):
    review_list: Optional[List[UserReviewDTO]] = []