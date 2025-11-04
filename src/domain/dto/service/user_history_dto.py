from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


#   request 는 user_like_dto.RequestUserLikeDto 로


class MergeUserHistory(BaseModel):
    id: str
    visited_at: datetime
    categories_name: str

class ResponseUserHistoryListDto(BaseModel):
    results: Optional[List[MergeUserHistory]]



class RequestUserHistoryDetailDto(BaseModel):
    user_id: str
    merge_history_id: str


class UserHistoryTDto(BaseModel):
    visited_at: datetime
    template_list: str