from typing import List, Optional

from pydantic import BaseModel, computed_field

"""

    찜, 내 리뷰, 내 방문 기록 요청

"""


class RequestSetUserLikeDTO(BaseModel):
    category_id: str


"""

    찜 목록 요청 응답

"""

class UserLikeDTO(BaseModel):
    type: str
    category_id: str
    category_name: str
    category_image: str
    sub_category: str
    do: Optional[str] = None
    si: Optional[str] = None
    gu: Optional[str] = None
    detail_address: str
    # category_address: str

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
        return UserLikeDTO(**d)

class ResponseUserLikeDTO(BaseModel):
    like_list: Optional[List[UserLikeDTO]] = []