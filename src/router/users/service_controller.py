import uuid
from typing import Dict

from fastapi import APIRouter, HTTPException, Request, Depends
from starlette.responses import JSONResponse

from src.domain.dto.service.haru_service_dto import (RequestStartMainServiceDTO, ResponseStartMainServiceDTO
, RequestChatServiceDTO, ResponseChatServiceDTO)
from src.logger.custom_logger import get_logger
from src.service.application.ai_service_handler import handle_modification_mode, handle_user_message, \
    handle_user_action_response
from src.service.application.main_screen_service import MainScreenService
from src.service.application.prompts import RESPONSE_MESSAGES
from src.service.auth.jwt import validate_jwt_token

router = APIRouter(
    prefix="/api/service",
    dependencies=[Depends(validate_jwt_token)]
)
logger = get_logger(__name__)

# 현재는 메모리 기반 딕셔너리 사용 (서버 재시작 시 초기화됨)
#   수정 예정
sessions: Dict[str, Dict] = {}


#   메인 화면: 로그인 후 바로 보여지는 화면
@router.post("/main")
async def to_main_screen(request: Request):
    main_service_class = MainScreenService()

    content = await main_service_class.to_main()
    return JSONResponse(
        content=content.model_dump()
    )

@router.get("/detail/{category_id}")
async def to_detail(category_id: str, request: Request):

    main_service_class = MainScreenService()
    content = await main_service_class.get_category_detail(category_id)
    return JSONResponse(
        content=content.model_dump()
    )


"""

    하루랑 채팅

"""

@router.post("/start")
async def start_conversation(data: RequestStartMainServiceDTO, request: Request):


    print(data.play_address)

    # 세션 ID 생성
    session_id = str(uuid.uuid4())

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


@router.get("/chat")
@router.post("/chat")
async def chat(request: RequestChatServiceDTO):

    # jwt = request.headers.jwt
    # if jwt is None:
    #     logger.error("Missing token")
    #     raise MissingTokenException()
    #
    # validate_result = await validate_jwt_token(jwt)
    # if validate_result == 2:
    #     logger.error("ExpiredToken token")
    #     raise ExpiredAccessTokenException()

    # 세션 확인
    if request.sessionId not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    session = sessions[request.sessionId]

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

    # 🔥 사용자 액션(Next/More 또는 Yes) 응답 처리 - await 추가!
    if session.get("waitingForUserAction", False):
        response = await handle_user_action_response(session, request.message)
        return JSONResponse(content=response.model_dump())

    # 일반 메시지 처리 (태그 생성)
    return JSONResponse(
        content=handle_user_message(session, request.message).model_dump()
    )
