from fastapi import Depends, HTTPException, APIRouter
from starlette.responses import JSONResponse

from src.domain.dto.chat.chat_message_dto import RequestChatMessageDTO, ResponseChatMessageDTO
from src.domain.dto.chat.chat_session_dto import RequestStartChatSessionDTO, ResponseStartChatSessionDTO
from src.domain.dto.history.history_dto import RequestSaveHistoryDTO
from src.domain.dto.transport.transport_dto import RequestCalculateTransportDTO, ResponseCalculateTransportDTO, \
    PublicTransportRouteDTO
from src.infra.cache.redis_repository import SessionRepository
from src.logger.custom_logger import get_logger
from src.service.application.conversation_handler import handle_user_message, handle_user_action_response, \
    save_selected_template_to_merge, save_selected_template
from src.service.application.prompts import RESPONSE_MESSAGES
from src.service.application.route_calculation_service import RouteCalculationService
from src.service.auth.jwt import get_jwt_user_id

session_repo = SessionRepository()

router = APIRouter(prefix="/api/service")
logger = get_logger(__name__)

@router.post("/start")
async def start_conversation(
        data: RequestStartChatSessionDTO,
        user_id: str = Depends(get_jwt_user_id)
) -> ResponseStartChatSessionDTO:

    chat_session_data = {
        "play_address": data.play_address,                      #   주소
        "peopleCount": data.peopleCount,                        #   인원수
        "selectedCategories": data.selectedCategories,          #   카테고리 타입
        "preselectedCategoryId": data.preselectedCategoryId,    #   미리 선택 된 매장
        "collectedTags": {},                                    #   카테고리별 태그 저장
        "currentCategoryIndex": 0,                              #   현재 질문 중인 카테고리
        "conversationHistory": [],                              #   대화 히스토리
        "stage": "collecting_details",                          #    현재 단계: collecting_details, confirming_results, completed
        "waitingForUserAction": False,                          #   사용자 액션(Next/More 또는 Yes) 대기 중인지
        "lastUserMessage": "",                                  #    마지막 사용자 메시지
        "pendingTags": [],                                      #   대기 중인 태그들
        "modificationMode": False,                              #   수정 모드인지
        "randomCategories": [],                                 #   추가 필요
        "randomCategoryPending": None,                          #   추가 필요
    }

    await session_repo.set_chat_session(
        user_id=user_id,
        chat_data=chat_session_data,
        ttl=1800    #   초
    )

    first_category = data.selectedCategories[0]
    categories_text = ', '.join(data.selectedCategories)

    first_message = RESPONSE_MESSAGES["start"]["first_message"].format(
        people_count=data.peopleCount,
        categories_text=categories_text,
        first_category=first_category
    )

    return ResponseStartChatSessionDTO(
        status="success",
        sessionId=user_id,
        message=first_message,
        stage="collecting_details",
        progress={
            "current": 0,
            "total": len(data.selectedCategories)
        }
    )


@router.post("/chat")
async def chat(
        request: RequestChatMessageDTO,
        user_id: str = Depends(get_jwt_user_id)
):

    session = await session_repo.get_chat_session(user_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="세션을 찾을 수 없습니다. 다시 시작해주세요."
        )

    # completed 상태 처리
    if session.get("stage") == "completed":
        return JSONResponse(
            content=ResponseChatMessageDTO(
                status="success",
                message="대화가 완료되었습니다. 새로운 대화를 시작하려면 처음부터 다시 시작해주세요.",
                stage="completed"
            ).model_dump()
        )

    # 사용자 액션 응답 처리
    if session.get("waitingForUserAction", False):
        response = await handle_user_action_response(session, request.message)
    else:
        response = handle_user_message(session, request.message)


    await session_repo.set_chat_session(
        user_id=user_id,
        chat_data=session,
        ttl=1800                #   초 단위
    )

    return JSONResponse(content=response.model_dump())


@router.post("/cal-route")
async def calculate_route(dto: RequestCalculateTransportDTO):
    dist = await RouteCalculationService().calculate_route_by_transport_type(
        transport_type=dto.transport_type,
        destination=dto.destination,
        origin=dto.origin,
    )

    routes = []

    if dist is None:
        return ResponseCalculateTransportDTO(
            duration=None,
            distance=None
        )

    if (dist is not None) and (dist.get("routes", 0) != 0):
        for i in dist.get("routes"):
            routes.append(
                PublicTransportRouteDTO(
                    description=i.get("description"),
                    duration_min=i.get("duration_minutes")
                )
            )

    result = ResponseCalculateTransportDTO(
        duration=dist.get("duration_seconds"),
        distance=dist.get("distance_meters"),
        routes=routes
    )

    return result


@router.post("/histories")
async def save_history(
        request: RequestSaveHistoryDTO,
        user_id: str = Depends(get_jwt_user_id)
):
    logger.info("save_history")

    await session_repo.delete_chat_session(user_id)

    merge_id = await save_selected_template_to_merge(dto=request, user_id=user_id)
    await save_selected_template(dto=request, merge_id=merge_id, user_id=user_id)

    return JSONResponse(
        status_code=200,
        content="success"
    )