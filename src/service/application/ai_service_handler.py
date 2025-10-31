"""
대화 흐름 제어 핸들러
"""

from typing import Dict

from src.domain.dto.service.haru_service_dto import ResponseChatServiceDTO
from src.service.application.prompts import RESPONSE_MESSAGES
from src.service.application.utils import extract_tags_by_category, format_collected_data_for_server


def handle_user_message(session: Dict, user_message: str) -> ResponseChatServiceDTO:
    """
    사용자 메시지 처리 및 태그 생성
    - 사용자가 입력한 내용에서 LLM을 통해 태그 추출
    - Next/More 버튼 표시
    """
    # 사용자 메시지 저장
    session["conversationHistory"].append({
        "role": "user",
        "message": user_message
    })
    session["lastUserMessage"] = user_message

    # 현재 카테고리 정보 확인
    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]

    # 인덱스 범위 확인
    if current_index >= len(selected_categories):
        # 모든 카테고리 완료 -> 결과 출력 확인 단계로 전환
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True  # 결과 출력 Yes 버튼 대기
        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,  # Yes 버튼 표시
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
            availableCategories=selected_categories
        )

    current_category = selected_categories[current_index]

    # 카테고리별 태그 추출 (LLM 사용)
    people_count = session.get("peopleCount", 1)
    new_tags = extract_tags_by_category(user_message, current_category, people_count)

    # collectedTags 초기화 확인
    if "collectedTags" not in session:
        session["collectedTags"] = {}

    # 기존 태그가 있는지 확인하고 추가
    if current_category in session["collectedTags"]:
        # 기존 태그가 있으면 새로운 태그와 합치기 (추가하기 선택한 경우)
        existing_tags = session["collectedTags"][current_category]
        combined_tags = existing_tags + new_tags
        # 중복 제거
        combined_tags = list(dict.fromkeys(combined_tags))  # 순서 유지하면서 중복 제거
        session["collectedTags"][current_category] = combined_tags
        session["pendingTags"] = combined_tags
    else:
        # 기존 태그가 없으면 새로운 태그만 사용
        session["collectedTags"][current_category] = new_tags
        session["pendingTags"] = new_tags

    tags = session["pendingTags"]

    # 태그 표시
    message = f"현재까지 수집된 키워드: {', '.join(tags)}"

    # Next/More 버튼 대기 상태로 전환
    session["waitingForUserAction"] = True

    return ResponseChatServiceDTO(
        status="success",
        message=message,
        stage="collecting_details",
        tags=tags,
        progress={
            "current": session["currentCategoryIndex"],
            "total": len(session["selectedCategories"])
        },
        showYesNoButtons=True,  # Next/More 버튼 표시
        yesNoQuestion="이 정보로 다음 질문으로 넘어가시겠습니까?",
        currentCategory=current_category
    )


def handle_user_action_response(session: Dict, user_response: str) -> ResponseChatServiceDTO:
    """
    사용자 버튼 액션 처리 (Next / More / Yes)

    대화 단계에 따라 다른 동작 수행:
    - collecting_details: Next(다음 카테고리) 또는 More(추가 입력)
    - confirming_results: Yes(최종 추천 생성)

    Args:
        session: 세션 데이터
        user_response: 사용자 응답 ("네", "추가하기" 등)

    Returns:
        다음 단계 응답
    """
    # 응답 파싱
    is_next = any(word in user_response.lower() for word in
                  ["yes", "네", "넵", "예", "좋아", "좋아요", "그래", "맞아", "ㅇㅇ", "기기", "ㄱㄱ", "고고", "네네", "다음"])
    is_more = any(word in user_response.lower() for word in ["추가", "더", "더해", "추가하기", "추가요", "더할래"])

    # 결과 출력 확인 단계: Yes(결과 출력) 처리
    if session.get("stage") == "confirming_results":
        if is_next:
            # 수집된 데이터를 구조화된 형식으로 변환
            collected_data = format_collected_data_for_server(session)

            # 대화 완료 상태로 전환
            session["stage"] = "completed"
            session["waitingForUserAction"] = False

            return ResponseChatServiceDTO(
                status="success",
                message=RESPONSE_MESSAGES["start"]["final_result"],
                stage="completed",
                recommendations=None,  # RECOMMENDATION_DATABASE 로직 제거
                collectedData=collected_data
            )
        else:
            # 명확하지 않은 응답 - 사용자 액션 대기 상태 유지
            return ResponseChatServiceDTO(
                status="success",
                message=RESPONSE_MESSAGES["start"]["unclear_result_response"],
                stage="confirming_results",
                showYesNoButtons=True,
                yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"]
            )

    # 태그 수집 단계: Next(다음 카테고리로) / More(현재 카테고리에 추가 입력) 처리
    if is_next and not is_more:
        return handle_next_category(session)
    elif is_more and not is_next:
        return handle_add_more_tags(session)
    else:
        # 명확하지 않은 응답 - 사용자 액션 대기 상태 유지
        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["unclear_response"],
            stage=session["stage"],
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["yes_no_question"]
        )


def handle_next_category(session: Dict) -> ResponseChatServiceDTO:
    """
    Next 버튼 처리

    현재 카테고리 태그 수집 완료 후 다음 카테고리로 이동.
    모든 카테고리 완료 시 결과 출력 확인 단계로 전환

    Args:
        session: 세션 데이터

    Returns:
        다음 카테고리 질문 또는 결과 확인 메시지
    """
    # 사용자 액션 대기 상태 해제
    session["waitingForUserAction"] = False

    # 현재 카테고리 정보
    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]

    # 인덱스 범위 확인
    if current_index >= len(selected_categories):
        # 이미 완료된 상태 -> 결과 출력 확인 단계로
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True  # Yes 버튼 대기
        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,  # Yes 버튼 표시
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
            availableCategories=selected_categories
        )

    # 다음 카테고리로 이동
    session["currentCategoryIndex"] += 1

    # 더 질문할 카테고리가 있는지 확인
    if session["currentCategoryIndex"] < len(selected_categories):
        # 다음 카테고리 질문
        next_category = selected_categories[session["currentCategoryIndex"]]
        next_message = RESPONSE_MESSAGES["start"]["next_category"].format(next_category=next_category)

        return ResponseChatServiceDTO(
            status="success",
            message=next_message,
            stage="collecting_details",
            progress={
                "current": session["currentCategoryIndex"],
                "total": len(selected_categories)
            }
        )
    else:
        # 모든 카테고리 완료 -> 결과 출력 확인 단계로
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True  # Yes 버튼 대기

        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,  # Yes 버튼 표시
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
            availableCategories=selected_categories
        )


def handle_modification_mode(session: Dict, user_message: str) -> ResponseChatServiceDTO:
    """
    수정 모드 처리 (현재 미사용) 태그 삭제 기능으로 사용할수도

    """


def handle_add_more_tags(session: Dict) -> ResponseChatServiceDTO:
    """
    More 버튼 처리

    사용자가 현재 카테고리에 대해 추가 정보를 입력하고 싶을 때.
    같은 카테고리에 대한 추가 태그가 기존 태그와 병합됨

    Args:
        session: 세션 데이터

    Returns:
        추가 입력 요청 메시지
    """
    # 사용자 액션 대기 상태 해제
    session["waitingForUserAction"] = False

    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]

    # 인덱스 범위 확인
    if current_index >= len(selected_categories):
        # 이미 완료된 상태 -> 결과 출력 확인 단계로
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True  # Yes 버튼 대기
        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,  # Yes 버튼 표시
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
            availableCategories=selected_categories
        )

    current_category = selected_categories[current_index]

    return ResponseChatServiceDTO(
        status="success",
        message=RESPONSE_MESSAGES["start"]["add_more"].format(current_category=current_category),
        stage="collecting_details",
        currentCategory=current_category
    )

