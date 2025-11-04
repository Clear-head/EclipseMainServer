from datetime import datetime

from pydantic import BaseModel


#   request 는 user_like_dto.RequestUserLikeDto 로

class ResponseUserHistoryListDto(BaseModel):
    visited_at: datetime
    template_list: list[str]

class UserHistoryTitleDto(BaseModel):
    visited_at: datetime
    template_list: str