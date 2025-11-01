"""

    내 리뷰 목록 요청 응답

"""
from typing import Optional, List

from pydantic import BaseModel

class RequestGetUserReviewDTO(BaseModel):
    user_id: str


class UserReviewDTO(BaseModel):
    review_id: str
    category_id: str
    category_name: str
    category_type: str
    comment: str
    stars: int

class ResponseUserReviewDTO(BaseModel):
    review_list: Optional[List[UserReviewDTO]] = []