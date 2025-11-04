from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


#   request 는 user_like_dto.RequestUserLikeDto 로

class RequestHistoryDto(BaseModel):
    user_id: str
    template_type: bool


"""

    일정표 히스토리 목록

"""
class MergeUserHistory(BaseModel):
    id: str
    visited_at: datetime
    categories_name: str

class ResponseUserHistoryListDto(BaseModel):
    results: Optional[List[MergeUserHistory]]


"""

    일정표 히스토리 디테일

"""
class RequestUserHistoryDetailDto(BaseModel):
    user_id: str
    merge_history_id: str


class UserHistoryDto(BaseModel):
    duration: int
    transportation_type: str
    category_id: int
    category_name: str

class ResponseUserHistoryDto(BaseModel):
    categories: list[UserHistoryDto]


"""

    일정표 저장

"""
class SelectedUserCategory(BaseModel):
    category_id: str
    category_name: str
    duration: int
    transportation: str


class RequestSetUserHistoryDto(BaseModel):
    user_id: str
    template_type: str
    category: list[SelectedUserCategory]