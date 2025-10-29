from typing import List, Optional

from pydantic import BaseModel

"""

    찜 목록 요청 응답

"""

class RequestUserLikeDTO(BaseModel):
    user_id: str


class ResponseUserLikeDTO(BaseModel):
    like_list: Optional[List] = []