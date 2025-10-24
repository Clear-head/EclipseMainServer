from typing import List, Optional
from pydantic import BaseModel

from src.domain.dto.header import JsonHeader


#   사용자 요청 형식
class RequestMainScreenDTO(BaseModel):
    headers: JsonHeader
    body: Optional[str] = None


#   사용자 응답 바디 내부 형식
class MainScreenCategoryList(BaseModel):
    id: str
    title: str
    image_url: str
    detail_address: str
    sub_category: str
    phone: Optional[str]
    # stars: int
    tags: List[str]


#   사용자 응답 바디 형식
class ResponseMainScreenBody(BaseModel):
    categories: List[MainScreenCategoryList]


#   사용자 응답 형식
class ResponseMainScreenDTO(BaseModel):
    headers: JsonHeader
    body: ResponseMainScreenBody