from typing import List, Optional

from pydantic import BaseModel

from src.domain.dto.category.category_dto import CategoryListItemDTO


# 좋아요 설정/해제 DTO

class RequestToggleLikeDTO(BaseModel):
    category_id: str


# 좋아요 목록 조회 DTO
class ResponseLikeListDTO(BaseModel):
    like_list: Optional[List[CategoryListItemDTO]] = []