from typing import List, Tuple
from pydantic import BaseModel
from blog_review import BlogReview
from datetime import datetime


class StoreInfo(BaseModel):
    title: str                      #   가게 이름
    address: str                    #   가게 주소
    phone: str                      #   가게 번호
    business_hours: str             #   영업 시간
    image: str                      #   가게 이미지 URL
    opinion: List[Tuple[str, int]]  #   이런점이 좋았어요 밑에 있는거
    content: List[str]              #   더 밑에 리뷰 내용
    blog_review: List[BlogReview]   #   블로그 리뷰 내용 리스트
    last_crawl: datetime            #   마지막 크롤링 시간