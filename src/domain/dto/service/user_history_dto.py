from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

#   request 는 user_like_dto.RequestUserLikeDto 로

"""

    일정표 히스토리 목록

"""
class MergeUserHistory(BaseModel):
    id: str
    visited_at: datetime
    categories_name: str
    template_type: str

class ResponseUserHistoryListDto(BaseModel):
    results: Optional[List[MergeUserHistory]]


"""

    일정표 히스토리 디테일

"""

class UserHistoryDto(BaseModel):
    duration: Optional[int] = None
    transportation: Optional[str] = None
    category_id: str
    category_name: str
    sub_category: str
    category_type: str
    category_detail_address: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    seq: int
    visited_at: datetime

class ResponseUserHistoryDto(BaseModel):
    categories: list[UserHistoryDto]
    template_type: str


"""

    일정표 저장

"""
class SelectedUserCategory(BaseModel):
    category_id: str
    category_name: str
    duration: Optional[int] = None
    transportation: Optional[str] = None
    description: Optional[str] = None


class RequestSetUserHistoryDto(BaseModel):
    template_type: str
    category: list[SelectedUserCategory]