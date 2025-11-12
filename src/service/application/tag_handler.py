"""
태그 관련 기능 처리 모듈
- 태그 액션 파싱 (삭제, 초기화)
- 태그 검증
- 태그 수집 및 관리
"""

from typing import Dict, Optional, Tuple

from src.domain.dto.chat.chat_message_dto import ResponseChatMessageDTO
from src.logger.custom_logger import get_logger
from src.service.application.prompts import RESPONSE_MESSAGES
from src.service.application.utils import (
    extract_tags_by_category,
    build_tags_progress_message,
    remove_tag_from_session,
    clear_tags_for_category
)

logger = get_logger(__name__)

# ==================== 태그 액션 상수 ====================
TAG_ACTION_PREFIX = "__TAG_ACTION__:"
TAG_ACTION_SEPARATOR = "::"
TAG_ACTION_REMOVE = "remove"
TAG_ACTION_CLEAR = "clear"


# ==================== 태그 액션 파싱 ====================
def parse_tag_action(user_response: str) -> Optional[Tuple[str, str, str]]:
    """
    태그 관련 사용자 액션 파싱
    
    Args:
        user_response: 사용자 응답 문자열
        
    Returns:
        (action, category, target_tag) 튜플 또는 None
        - action: remove | clear
        - category: 카테고리명
        - tag: 제거할 태그 (clear의 경우 생략 가능)
    """
    if not user_response or not user_response.startswith(TAG_ACTION_PREFIX):
        return None

    payload = user_response[len(TAG_ACTION_PREFIX):]
    parts = payload.split(TAG_ACTION_SEPARATOR, 2)

    if len(parts) < 2:
        return None

    action = parts[0].strip().lower()
    category = parts[1].strip()
    target_tag = parts[2].strip() if len(parts) > 2 else ""

    return action, category, target_tag


# ==================== 태그 삭제/초기화 핸들러 ====================
def handle_tag_clear(session: Dict, category: str, build_progress_func) -> ResponseChatMessageDTO:
    """
    태그 전체 삭제 처리
    
    Args:
        session: 현재 세션
        category: 카테고리명
        build_progress_func: 진행 상황 생성 함수
    """
    clear_tags_for_category(session, category)
    session["waitingForUserAction"] = False

    cleared_message = RESPONSE_MESSAGES["tags"]["cleared"]
    reask_template = RESPONSE_MESSAGES["start"]["reask_category"]
    message = f"{cleared_message}\n\n{reask_template.format(current_category=category)}"

    return ResponseChatMessageDTO(
        status="success",
        message=message,
        stage="collecting_details",
        tags=[],
        progress=build_progress_func(session),
        showYesNoButtons=False,
        currentCategory=category
    )


def handle_tag_remove(session: Dict, category: str, target_tag: str, build_progress_func) -> ResponseChatMessageDTO:
    """
    특정 태그 삭제 처리
    
    Args:
        session: 현재 세션
        category: 카테고리명
        target_tag: 삭제할 태그
        build_progress_func: 진행 상황 생성 함수
    """
    collected_tags = session.setdefault("collectedTags", {})
    existing_tags = collected_tags.get(category, [])

    # 태그가 없거나 삭제할 태그가 없는 경우
    if not existing_tags or target_tag not in existing_tags:
        not_found_message = RESPONSE_MESSAGES["tags"].get("not_found", "삭제할 태그를 찾지 못했어.")
        current_message = build_tags_progress_message(existing_tags) if existing_tags else ""
        combined_message = not_found_message if not current_message else f"{not_found_message}\n\n{current_message}"

        session["waitingForUserAction"] = bool(existing_tags)

        return ResponseChatMessageDTO(
            status="success",
            message=combined_message,
            stage="collecting_details",
            tags=existing_tags or None,
            progress=build_progress_func(session),
            showYesNoButtons=bool(existing_tags),
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["yes_no_question"] if existing_tags else None,
            currentCategory=category
        )

    # 태그 삭제
    updated_tags = remove_tag_from_session(session, category, target_tag)
    removed_message = RESPONSE_MESSAGES["tags"]["removed"].format(removed_tag=target_tag)

    # 남은 태그가 있는 경우
    if updated_tags:
        current_message = build_tags_progress_message(updated_tags)
        combined_message = f"{removed_message}\n\n{current_message}"

        session["waitingForUserAction"] = True

        return ResponseChatMessageDTO(
            status="success",
            message=combined_message,
            stage="collecting_details",
            tags=updated_tags,
            progress=build_progress_func(session),
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["yes_no_question"],
            currentCategory=category
        )

    # 모든 태그가 삭제된 경우
    session["waitingForUserAction"] = False
    reask_template = RESPONSE_MESSAGES["start"]["reask_category"]
    message = f"{removed_message}\n\n{RESPONSE_MESSAGES['tags']['cleared']}\n\n{reask_template.format(current_category=category)}"

    return ResponseChatMessageDTO(
        status="success",
        message=message,
        stage="collecting_details",
        tags=[],
        progress=build_progress_func(session),
        showYesNoButtons=False,
        currentCategory=category
    )


def handle_tag_action(session: Dict, user_response: str, get_current_category_func, build_progress_func) -> Optional[ResponseChatMessageDTO]:
    """
    태그 액션 (삭제/초기화) 처리
    
    Args:
        session: 현재 세션
        user_response: 사용자 응답
        get_current_category_func: 현재 카테고리 조회 함수
        build_progress_func: 진행 상황 생성 함수
    """
    parsed = parse_tag_action(user_response)
    if not parsed:
        return None

    action, category, target_tag = parsed
    current_category = get_current_category_func(session)

    # 카테고리 보정
    if not category:
        category = current_category

    if not category:
        message = RESPONSE_MESSAGES["validation"]["ambiguous"]
        session["waitingForUserAction"] = False
        return ResponseChatMessageDTO(
            status="validation_failed",
            message=message,
            stage="collecting_details",
        )

    if action == TAG_ACTION_CLEAR:
        return handle_tag_clear(session, category, build_progress_func)
    elif action == TAG_ACTION_REMOVE:
        return handle_tag_remove(session, category, target_tag, build_progress_func)

    return None


# ==================== 태그 수집 ====================
def collect_tags_from_message(
    session: Dict,
    user_message: str,
    current_category: str,
    people_count: int
) -> Dict:
    """
    사용자 메시지에서 태그 추출 및 수집
    
    Args:
        session: 현재 세션
        user_message: 사용자 메시지
        current_category: 현재 카테고리
        people_count: 인원 수
        
    Returns:
        추출된 태그 정보 딕셔너리
    """
    new_tags = extract_tags_by_category(user_message, current_category, people_count)

    collected_tags = session.setdefault("collectedTags", {})

    # 기존 태그와 병합 (중복 제거)
    if current_category in collected_tags:
        existing_tags = collected_tags[current_category]
        combined_tags = list(dict.fromkeys(existing_tags + new_tags))
        collected_tags[current_category] = combined_tags
        session["pendingTags"] = combined_tags
    else:
        collected_tags[current_category] = new_tags
        session["pendingTags"] = new_tags

    return {
        "tags": session["pendingTags"],
        "message": build_tags_progress_message(session["pendingTags"])
    }