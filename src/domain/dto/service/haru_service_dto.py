from typing import Dict, List, Optional

from pydantic import BaseModel


#   /api/service/start

#   대화 시작 요청 모델
class RequestStartMainServiceDTO(BaseModel):
    play_address: str
    peopleCount: int  # 함께할 인원 수
    selectedCategories: List[str]  # 선택한 활동 카테고리 (예: ["카페", "음식점"])


#   대화 시작 응답 모델
class ResponseStartMainServiceDTO(BaseModel):
    status: str  # 상태 (success/error)
    sessionId: str  # 생성된 세션 ID
    message: str  # 챗봇 메시지
    stage: str  # 현재 대화 단계
    progress: Dict[str, int]  # 진행 상태 (current, total)




#   /api/service/chat
#   채팅 메시지 요청 모델 바디
class RequestChatServiceDTO(BaseModel):
    sessionId: str  # 세션 식별자
    message: str  # 사용자 메시지


#   채팅 응답 모델
class ResponseChatServiceDTO(BaseModel):
    status: str  # 상태
    message: str  # 챗봇 메시지
    stage: str  # 현재 대화 단계
    tags: Optional[List[str]] = None  # 추출된 태그 목록
    progress: Optional[Dict[str, int]] = None  # 진행 상태
    recommendations: Optional[Dict[str, List[str]]] = None  # 최종 추천 결과

    # Flutter 클라이언트 호환성을 위한 필드 (이름은 yesNo지만 실제로는 Next/More 또는 Yes 버튼)
    showYesNoButtons: Optional[bool] = False  # 버튼 표시 여부
    yesNoQuestion: Optional[str] = None  # 버튼과 함께 보여줄 질문
    currentCategory: Optional[str] = None  # 현재 질문 중인 카테고리
    availableCategories: Optional[List[str]] = None  # 선택 가능한 카테고리 목록
