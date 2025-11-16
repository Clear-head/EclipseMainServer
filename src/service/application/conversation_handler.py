"""
대화 흐름 제어 핸들러
- 사용자 메시지 처리
- 버튼 액션 처리
- 단계별 진행 관리
"""

from typing import Dict, Optional

from src.domain.dto.chat.chat_message_dto import ResponseChatMessageDTO
from src.domain.dto.chat.chat_recommendation_dto import ResponseChatRecommendationDTO
from src.domain.dto.history.history_dto import RequestSaveHistoryDTO
from src.domain.entities.merge_history_entity import MergeHistoryEntity
from src.domain.entities.user_history_entity import UserHistoryEntity
from src.infra.database.repository.merge_history_repository import MergeHistoryRepository
from src.infra.database.repository.user_history_repository import UserHistoryRepository
from src.logger.custom_logger import get_logger
from src.service.application.prompts import RESPONSE_MESSAGES
from src.service.application.recommendation_handler import (
    get_store_recommendations
)
# 분리된 모듈 임포트
from src.service.application.tag_handler import (
    handle_tag_action,
    collect_tags_from_message
)
from src.service.application.utils import (
    validate_user_input,
    format_collected_data_for_server
)

logger = get_logger(__name__)

# ==================== 응답 키워드 ====================
POSITIVE_KEYWORDS = [
    "yes", "응", "고", "네", "넵", "예", "좋아", "좋아요", 
    "그래", "맞아", "ㅇㅇ", "기기", "ㄱㄱ", "고고", "네네", 
    "다음", "다음 질문", "다음질문"
]
MORE_KEYWORDS = ["추가", "더", "더해", "추가하기", "추가요", "더할래"]


# ==================== 세션 헬퍼 함수 ====================
def get_current_category(session: Dict) -> Optional[str]:
    """현재 진행 중인 카테고리 반환"""
    selected_categories = session.get("selectedCategories", [])
    current_index = session.get("currentCategoryIndex", 0)

    if 0 <= current_index < len(selected_categories):
        return selected_categories[current_index]
    return None


def build_progress(session: Dict) -> Optional[Dict[str, int]]:
    """진행 상황 정보 생성"""
    selected_categories = session.get("selectedCategories", [])
    current_index = session.get("currentCategoryIndex", 0)
    
    if not selected_categories:
        return None
        
    return {
        "current": current_index,
        "total": len(selected_categories)
    }


def is_positive_response(user_response: str) -> bool:
    """긍정 응답 여부 확인"""
    return any(keyword in user_response.lower() for keyword in POSITIVE_KEYWORDS)


def is_more_response(user_response: str) -> bool:
    """추가 요청 응답 여부 확인"""
    return any(keyword in user_response.lower() for keyword in MORE_KEYWORDS)


# ==================== 메시지 핸들러 ====================
def handle_user_message(session: Dict, user_message: str) -> ResponseChatMessageDTO:
    """
    사용자 메시지 처리 및 태그 생성

    Args:
        session: 현재 세션
        user_message: 사용자 메시지
    """
    # 대화 기록 저장
    session["conversationHistory"].append({
        "role": "user",
        "message": user_message
    })
    session["lastUserMessage"] = user_message

    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]

    # 모든 카테고리 완료 확인
    if current_index >= len(selected_categories):
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True
        return ResponseChatMessageDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
            availableCategories=selected_categories
        )

    current_category = selected_categories[current_index]
    people_count = session.get("peopleCount", 1)

    # LLM으로 입력 검증 및 랜덤 판별
    result_type, error_message = validate_user_input(user_message, current_category)

    # Case 1: 랜덤 추천 요청
    if result_type == "random":
        logger.info(f"LLM 판단: 랜덤 추천 요청 - '{user_message}'")

        session.setdefault("collectedTags", {})
        session.setdefault("randomCategories", [])
        session["randomCategoryPending"] = current_category
        session["stage"] = "confirming_random"
        session["waitingForUserAction"] = True

        return ResponseChatMessageDTO(
            status="success",
            message=RESPONSE_MESSAGES["random"]["ask"],
            stage="confirming_random",
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["random"]["ask_question"],
            currentCategory=current_category,
            progress=build_progress(session)
        )

    # Case 2: 의미없는 입력
    if result_type == "invalid":
        logger.warning(f"LLM 판단: 의미없는 입력 - '{user_message}'")
        return ResponseChatMessageDTO(
            status="validation_failed",
            message=error_message,
            stage="collecting_details",
            currentCategory=current_category
        )

    # Case 3: 의미있는 입력 → 태그 추출 (분리된 모듈 사용)
    logger.info(f"LLM 판단: 의미있는 입력 - '{user_message}'")

    tag_result = collect_tags_from_message(session, user_message, current_category, people_count)
    session["waitingForUserAction"] = True

    return ResponseChatMessageDTO(
        status="success",
        message=tag_result["message"],
        stage="collecting_details",
        tags=tag_result["tags"],
        progress=build_progress(session),
        showYesNoButtons=True,
        yesNoQuestion=RESPONSE_MESSAGES["buttons"]["yes_no_question"],
        currentCategory=current_category
    )


# ==================== 액션 응답 핸들러 ====================
async def handle_user_action_response(session: Dict, user_response: str):
    """
    사용자 버튼 액션 처리 (Next / More / Yes)

    Args:
        session: 현재 세션
        user_response: 사용자 응답
    """
    # 태그 액션 처리 (우선순위) - 분리된 모듈 사용
    tag_action_response = handle_tag_action(
        session,
        user_response,
        get_current_category,
        build_progress
    )
    if tag_action_response:
        return tag_action_response

    is_next = is_positive_response(user_response)
    is_more = is_more_response(user_response)

    # 랜덤 추천 확인 단계
    if session.get("stage") == "confirming_random":
        return await handle_random_confirmation(session, is_next)

    # 결과 출력 확인 단계
    if session.get("stage") == "confirming_results":
        return await handle_results_confirmation(session, is_next)

    # 태그 수집 단계
    if is_next and not is_more:
        return handle_next_category(session)
    elif is_more and not is_next:
        return handle_add_more_tags(session)
    else:
        return ResponseChatMessageDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["unclear_response"],
            stage=session["stage"],
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["yes_no_question"]
        )


# ==================== 단계별 확인 핸들러 ====================
async def handle_random_confirmation(session: Dict, is_confirmed: bool) -> ResponseChatMessageDTO:
    """랜덤 추천 확인 처리"""
    pending_category = session.get("randomCategoryPending")

    if not pending_category:
        session["stage"] = "collecting_details"
        session["waitingForUserAction"] = False
        return ResponseChatMessageDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["unclear_response"],
            stage="collecting_details",
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["yes_no_question"]
        )

    if is_confirmed:
        # 랜덤 카테고리로 등록
        random_categories = session.setdefault("randomCategories", [])
        if pending_category not in random_categories:
            random_categories.append(pending_category)

        collected_tags = session.setdefault("collectedTags", {})
        collected_tags.setdefault(pending_category, [])

        session["randomCategoryPending"] = None
        session["waitingForUserAction"] = False
        session["stage"] = "collecting_details"

        # 다음 카테고리로 이동
        next_response = handle_next_category(session)
        ready_message = RESPONSE_MESSAGES["random"]["ready"]

        if next_response.message:
            next_response.message = f"{ready_message}\n\n{next_response.message}"
        else:
            next_response.message = ready_message

        session["stage"] = next_response.stage
        return next_response
    else:
        # 랜덤 거부
        session["randomCategoryPending"] = None
        session["waitingForUserAction"] = False
        session["stage"] = "collecting_details"

        current_category = get_current_category(session) or pending_category

        return ResponseChatMessageDTO(
            status="success",
            message=RESPONSE_MESSAGES["random"]["decline"],
            stage="collecting_details",
            currentCategory=current_category,
            progress=build_progress(session),
            showYesNoButtons=False
        )


async def handle_results_confirmation(session: Dict, is_confirmed: bool):
    """결과 확인 처리 (매장 추천 생성)"""
    if is_confirmed:
        logger.info("confirming_results 단계에서 '네' 선택 -> 매장 추천 생성")

        # 수집된 데이터 구조화
        collected_data = format_collected_data_for_server(session)

        # 매장 추천 생성 (분리된 모듈 사용)
        recommendations = await get_store_recommendations(session)

        # 세션에 저장
        session["recommendations"] = recommendations
        session["stage"] = "completed"
        session["waitingForUserAction"] = False

        return ResponseChatRecommendationDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["final_result"],
            stage="completed",
            recommendations=recommendations,
            collectedData=collected_data
        )
    else:
        return ResponseChatMessageDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["unclear_result_response"],
            stage="confirming_results",
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"]
        )


# ==================== 카테고리 네비게이션 ====================
def handle_next_category(session: Dict) -> ResponseChatMessageDTO:
    """다음 카테고리로 이동"""
    session["waitingForUserAction"] = False
    session["currentCategoryIndex"] += 1

    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]

    # 다음 카테고리가 있는 경우
    if current_index < len(selected_categories):
        next_category = selected_categories[current_index]
        next_message = RESPONSE_MESSAGES["start"]["next_category"].format(next_category=next_category)

        return ResponseChatMessageDTO(
            status="success",
            message=next_message,
            stage="collecting_details",
            progress=build_progress(session)
        )

    # 모든 카테고리 완료
    session["stage"] = "confirming_results"
    session["waitingForUserAction"] = True

    return ResponseChatMessageDTO(
        status="success",
        message=RESPONSE_MESSAGES["start"]["all_completed"],
        stage="confirming_results",
        showYesNoButtons=True,
        yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
        availableCategories=selected_categories
    )


def handle_add_more_tags(session: Dict) -> ResponseChatMessageDTO:
    """추가 태그 입력 요청"""
    session["waitingForUserAction"] = False

    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]

    if current_index >= len(selected_categories):
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True
        return ResponseChatMessageDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
            availableCategories=selected_categories
        )

    current_category = selected_categories[current_index]

    return ResponseChatMessageDTO(
        status="success",
        message=RESPONSE_MESSAGES["start"]["add_more"].format(current_category=current_category),
        stage="collecting_details",
        currentCategory=current_category
    )


# ==================== 히스토리 저장 ====================
async def save_selected_template_to_merge(dto: RequestSaveHistoryDTO, user_id: str) -> str:
    """일정표 병합 히스토리 저장"""
    logger.info(f"병합 히스토리 저장 시작: user_id={user_id}")

    try:
        # 카테고리 이름 포맷팅
        if dto.template_type == "0":
            name = ", ".join([category.category_name for category in dto.category])
        else:
            name = "→".join([category.category_name for category in dto.category])

        # 엔티티 생성 및 저장
        repo = MergeHistoryRepository()
        entity = MergeHistoryEntity.from_dto(
            user_id=user_id,
            categories_name=name,
            template_type=dto.template_type,
        )

        await repo.insert(entity)

        logger.info(f"병합 히스토리 저장 성공: merge_id={entity.id}")
        return entity.id

    except Exception as e:
        logger.error(f"병합 히스토리 저장 실패: {e}", exc_info=True)
        raise e


async def save_selected_template(dto: RequestSaveHistoryDTO, merge_id: str, user_id: str) -> bool:
    """개별 일정 히스토리 저장"""
    logger.info(f"일정 히스토리 저장 시작: user_id={user_id}, merge_id={merge_id}")

    try:
        repo = UserHistoryRepository()

        for index, category_data in enumerate(dto.category):
            entity = UserHistoryEntity.from_dto(
                user_id=user_id,
                seq=index,
                merge_id=merge_id,
                **category_data.model_dump()
            )
            await repo.insert(entity)

        logger.info(f"일정 히스토리 저장 성공: {len(dto.category)}개 항목")
        return True

    except Exception as e:
        logger.error(f"일정 히스토리 저장 실패: {e}", exc_info=True)
        raise e