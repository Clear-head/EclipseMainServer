from typing import List, Dict
from pydantic import BaseModel


# 채팅 세션 시작 DTO
class RequestStartChatSessionDTO(BaseModel):
    play_address: str                    # 활동 지역
    peopleCount: int                     # 인원 수
    selectedCategories: List[str]        # 선택한 카테고리 (예: ["카페", "음식점"])


class ResponseStartChatSessionDTO(BaseModel):
    status: str                          # 상태 (success/error)
    sessionId: str                       # 생성된 세션 ID
    message: str                         # 챗봇 메시지
    stage: str                           # 현재 대화 단계
    progress: Dict[str, int]             # 진행 상태 (current, total)