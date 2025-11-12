from typing import List, Optional, Dict

from pydantic import BaseModel

from src.domain.dto.category.category_dto import CategoryListItemDTO


# =============================================================================
# 추천 결과 관련 DTO
# =============================================================================

class RecommendationItemDTO(BaseModel):
    """추천 매장 아이템"""
    id: str
    title: str
    image_url: str
    detail_address: str
    sub_category: str
    lat: Optional[str] = None
    lng: Optional[str] = None


class CollectedDataItemDTO(BaseModel):
    """수집된 데이터 아이템"""
    location: str
    human_count: str
    category_type: str
    keywords: List[str]


class ResponseChatRecommendationDTO(BaseModel):
    """채팅 추천 결과 응답"""
    status: str
    message: str
    stage: str
    recommendations: Optional[Dict[str, List[CategoryListItemDTO]]] = None
    collectedData: Optional[List[CollectedDataItemDTO]] = None