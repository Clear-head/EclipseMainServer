from typing import List, Optional, Dict

from pydantic import BaseModel


# 채팅 메시지 요청 DTO
class RequestChatMessageDTO(BaseModel):
    message: str


# 채팅 메시지 응답 DTO (기본)
class ResponseChatMessageDTO(BaseModel):
    status: str  # 상태
    message: str  # 챗봇 메시지
    stage: str  # 현재 대화 단계
    tags: Optional[List[str]] = None  # 추출된 태그 목록
    progress: Optional[Dict[str, int]] = None  # 진행 상태

    # 버튼 관련
    showYesNoButtons: Optional[bool] = False
    yesNoQuestion: Optional[str] = None

    # 카테고리 관련
    currentCategory: Optional[str] = None
    availableCategories: Optional[List[str]] = None