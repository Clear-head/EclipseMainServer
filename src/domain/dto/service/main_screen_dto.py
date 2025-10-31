from typing import List, Optional

from pydantic import BaseModel


#   사용자 요청 형식
class RequestMainScreenDTO(BaseModel):
    body: Optional[str] = None


#   사용자 응답 바디 형식
class MainScreenCategoryList(BaseModel):
    id: str
    title: str
    image_url: str
    detail_address: str
    sub_category: str
    # stars: int


#   사용자 응답 형식
class ResponseMainScreenDTO(BaseModel):
    categories: List[MainScreenCategoryList]
