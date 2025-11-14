from typing import List, Optional

from pydantic import BaseModel, computed_field


# 좋아요 설정/해제 DTO

class RequestToggleLikeDTO(BaseModel):
    category_id: str


# 좋아요 목록 조회 DTO

class LikeItemDTO(BaseModel):
    type: str
    category_id: str
    category_name: str
    category_image: str
    sub_category: str
    do: Optional[str] = None
    si: Optional[str] = None
    gu: Optional[str] = None
    detail_address: str
    review_count: Optional[int] = 0
    average_rating: Optional[float] = 0.0

    @computed_field
    @property
    def category_address(self) -> str:
        return (
            f"{self.do or ''}"
            f"{self.si or ''}"
            f"{self.gu or ''}"
            f"{self.detail_address or ''}"
        ).strip()

    @classmethod
    def from_dict(cls, d: dict):
        return LikeItemDTO(**d)


class ResponseLikeListDTO(BaseModel):
    like_list: Optional[List[LikeItemDTO]] = []