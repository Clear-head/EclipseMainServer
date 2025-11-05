from typing import Dict

from fastapi import APIRouter, HTTPException, Depends
from starlette.responses import JSONResponse

from src.domain.dto.service.haru_service_dto import (RequestStartMainServiceDTO, ResponseStartMainServiceDTO
, RequestChatServiceDTO, ResponseChatServiceDTO)
from src.domain.dto.service.user_history_dto import RequestSetUserHistoryDto
from src.logger.custom_logger import get_logger
from src.service.application.ai_service_handler import handle_modification_mode, handle_user_message, \
    handle_user_action_response, save_selected_template_to_merge, save_selected_template
from src.service.application.prompts import RESPONSE_MESSAGES
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(
    prefix="/api/service"
)
logger = get_logger(__name__)

# 현재는 메모리 기반 딕셔너리 사용 (서버 재시작 시 초기화됨)
#   수정 예정
sessions: Dict[str, Dict] = {}

"""

    하루랑 채팅

"""

@router.post("/start")
async def start_conversation(data: RequestStartMainServiceDTO, user_id:str = Depends(get_jwt_user_id)):

    # 세션 ID 생성
    session_id = user_id

    # 세션 데이터 초기화
    sessions[session_id] = {
        "play_address": data.play_address,
        "peopleCount": data.peopleCount,
        "selectedCategories": data.selectedCategories,
        "collectedTags": {},  # 카테고리별 태그 저장
        "currentCategoryIndex": 0,  # 현재 질문 중인 카테고리
        "conversationHistory": [],  # 대화 히스토리
        "stage": "collecting_details",  # 현재 단계: collecting_details, confirming_results, completed
        "waitingForUserAction": False,  # 사용자 액션(Next/More 또는 Yes) 대기 중인지
        "lastUserMessage": "",  # 마지막 사용자 메시지
        "pendingTags": [],  # 대기 중인 태그들
        "modificationMode": False,  # 수정 모드인지
    }

    # 첫 번째 카테고리에 대한 질문 생성 (인원수와 카테고리 정보 포함)
    first_category = data.selectedCategories[0]
    categories_text = ', '.join(data.selectedCategories)

    first_message = RESPONSE_MESSAGES["start"]["first_message"].format(
        people_count=data.peopleCount,
        categories_text=categories_text,
        first_category=first_category
    )

    response = ResponseStartMainServiceDTO(
        status="success",
        sessionId=session_id,
        message=first_message,
        stage="collecting_details",
        progress={
            "current": 0,
            "total": len(data.selectedCategories)
        }
    )

    return JSONResponse(
        content=response.model_dump()
    )


#   메시지 전송
@router.post("/chat")
async def chat(request: RequestChatServiceDTO, user_id:str = Depends(get_jwt_user_id)):

    # 세션 확인
    if user_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    session = sessions[user_id]

    # completed 상태 처리 - 대화 완료 후 추가 메시지
    if session.get("stage") == "completed":

        contents = ResponseChatServiceDTO(
                status="success",
                message="대화가 완료되었습니다. 새로운 대화를 시작하려면 처음부터 다시 시작해주세요.",
                stage="completed"
        )

        return JSONResponse(
            content=contents.model_dump()
        )

    # modification_mode 처리
    if session.get("stage") == "modification_mode":

        return JSONResponse(
            content=handle_modification_mode(session, request.message).model_dump()
        )

    # 사용자 액션(Next/More 또는 Yes) 응답 처리
    if session.get("waitingForUserAction", False):
        response = await handle_user_action_response(session, request.message)
        return JSONResponse(content=response.model_dump())

    # 일반 메시지 처리 (태그 생성)
    return JSONResponse(
        content=handle_user_message(session, request.message).model_dump()
    )


@router.post("/histories")
async def save_history(request: RequestSetUserHistoryDto, user_id:str = Depends(get_jwt_user_id)):
    logger.info("save_history")
    merge_id = await save_selected_template_to_merge(dto=request, user_id=user_id)
    await save_selected_template(dto=request, merge_id=merge_id, user_id=user_id)

    return JSONResponse(
        status_code=200,
        content="success"
    )