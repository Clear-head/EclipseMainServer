import uuid
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from src.domain.dto.header import JsonHeader
from src.domain.dto.service.haru_service_dto import RequestStartMainServiceDTO, ResponseStartMainServiceDTO, \
    StartResponseBody, RequestChatServiceDTO, ChatResponseBody, ResponseChatServiceDTO
from src.domain.dto.service.main_screen_dto import RequestMainScreenDTO
from src.logger.custom_logger import get_logger
from src.service.application.ai_service_handler import handle_modification_mode, handle_user_message, \
    handle_user_action_response
from src.service.application.main_screen_service import MainScreenService
from src.service.application.prompts import RESPONSE_MESSAGES
from src.service.auth.jwt import validate_jwt_token
from src.utils.exception_handler.auth_error_class import MissingTokenException, ExpiredAccessTokenException

router = APIRouter(prefix="/api/service")
logger = get_logger(__name__)

# 현재는 메모리 기반 딕셔너리 사용 (서버 재시작 시 초기화됨)
#   수정 예정
sessions: Dict[str, Dict] = {}


#   메인 화면: 로그인 후 바로 보여지는 화면
@router.post("/main")
async def to_main_screen(request: Request):
    jwt = request.headers.get("jwt")

    if jwt is None:
        logger.error("Missing token")
        raise MissingTokenException()

    validate_result = await validate_jwt_token(jwt)

    if validate_result == 2:
        logger.error("Expired token")
        raise ExpiredAccessTokenException()

    main_service_class = MainScreenService()
    return await main_service_class.to_main()


@router.post("/start")
async def start_conversation(request: RequestStartMainServiceDTO) -> ResponseStartMainServiceDTO:

    jwt = request.headers.jwt
    if jwt is None:
        logger.error("Missing token")
        raise MissingTokenException()

    validate_result = await validate_jwt_token(jwt)
    if validate_result == 2:
        logger.error("ExpiredToken token")
        raise ExpiredAccessTokenException()

    # 세션 ID 생성
    session_id = str(uuid.uuid4())

    # 세션 데이터 초기화
    sessions[session_id] = {
        "peopleCount": request.body.peopleCount,
        "selectedCategories": request.body.selectedCategories,
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
    first_category = request.body.selectedCategories[0]
    categories_text = ', '.join(request.body.selectedCategories)

    first_message = RESPONSE_MESSAGES["start"]["first_message"].format(
        people_count=request.body.peopleCount,
        categories_text=categories_text,
        first_category=first_category
    )

    response = ResponseStartMainServiceDTO(
        headers=JsonHeader(
            jwt=request.headers.jwt,
        ),
        body=StartResponseBody(
            status="success",
            sessionId=session_id,
            message=first_message,
            stage="collecting_details",
            progress={
                "current": 0,
                "total": len(request.body.selectedCategories)
            }
        )
    )

    return response


@router.get("/chat")
@router.post("/chat")
async def chat(request: RequestChatServiceDTO) -> ResponseChatServiceDTO:

    jwt = request.headers.jwt
    if jwt is None:
        logger.error("Missing token")
        raise MissingTokenException()

    validate_result = await validate_jwt_token(jwt)
    if validate_result == 2:
        logger.error("ExpiredToken token")
        raise ExpiredAccessTokenException()

    # 세션 확인
    if request.body.sessionId not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    session = sessions[request.body.sessionId]

    # completed 상태 처리 - 대화 완료 후 추가 메시지
    if session.get("stage") == "completed":
        return ResponseChatServiceDTO(
            headers=JsonHeader(
                jwt=request.headers.jwt,
            ),
            body=ChatResponseBody(
                status="success",
                message="대화가 완료되었습니다. 새로운 대화를 시작하려면 처음부터 다시 시작해주세요.",
                stage="completed"
            )
        )

    # modification_mode 처리
    if session.get("stage") == "modification_mode":
        return ResponseChatServiceDTO(
            headers=JsonHeader(
                jwt=request.headers.jwt,
            ),
            body=handle_modification_mode(session, request.body.message)
        )

    # 사용자 액션(Next/More 또는 Yes) 응답 처리
    if session.get("waitingForUserAction", False):
        return ResponseChatServiceDTO(
            headers=JsonHeader(
                jwt=request.headers.jwt,
            ),
            body=handle_user_action_response(session, request.body.message)
        )

    # 일반 메시지 처리 (태그 생성)
    return ResponseChatServiceDTO(
        headers=JsonHeader(
            jwt=request.headers.jwt,
        ),
        body=handle_user_message(session, request.body.message)
    )
