from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# 방문 기록 목록 조회 DTO
class HistoryListItemDTO(BaseModel):
    id: str
    visited_at: datetime
    categories_name: str
    template_type: str


class ResponseHistoryListDTO(BaseModel):
    results: Optional[List[HistoryListItemDTO]]


# 방문 기록 상세 조회 DTO
class HistoryDetailItemDTO(BaseModel):
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


class ResponseHistoryDetailDTO(BaseModel):
    categories: List[HistoryDetailItemDTO]
    template_type: str


# 방문 기록 저장 DTO
class HistoryCategoryItemDTO(BaseModel):
    category_id: str
    category_name: str
    duration: Optional[int] = None
    transportation: Optional[str] = None
    description: Optional[str] = None


class RequestSaveHistoryDTO(BaseModel):
    template_type: str
    category: List[HistoryCategoryItemDTO]


# 방문 횟수 조회 DTO
class ResponseVisitCountDTO(BaseModel):
    visit_count: int