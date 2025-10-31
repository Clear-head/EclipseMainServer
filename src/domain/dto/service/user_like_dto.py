from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

"""

    찜, 내 리뷰, 내 방문 기록 요청

"""

class RequestGetUserLikeDTO(BaseModel):
    user_id: str


class RequestSetUserLikeDTO(BaseModel):
    category_id: str
    user_id: str


"""

    찜 목록 요청 응답

"""

class UserLikeDTO(BaseModel):
    type: str
    category_id: str
    category_name: str
    category_image: str
    sub_category: str
    do: Optional[str]
    si: Optional[str]
    gu: Optional[str]
    detail_address: str
    category_address: str = Field(
        default_factory=lambda x: f"{x['do'] }{x['si'] }{x['gu'] }{x['detail_address']}"
    )


    @classmethod
    def from_dict(cls, d: dict):
        return UserLikeDTO(**d)

class ResponseUserLikeDTO(BaseModel):
    like_list: Optional[List[UserLikeDTO]] = []


"""

    내 방문 기록 요청 응답

"""
class UserHistoryDTO(BaseModel):
    category_id: str
    category_name: str
    visited_at: datetime


class ResponseUserHistoryDTO(BaseModel):
    history_list: Optional[List[UserHistoryDTO]] = []
