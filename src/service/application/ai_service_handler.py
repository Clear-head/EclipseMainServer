"""
대화 흐름 제어 핸들러 (추천 생성 + GPT 필터링 호출)
"""

from typing import Dict, List

from src.domain.dto.service.haru_service_dto import ResponseChatServiceDTO
from src.domain.dto.service.main_screen_dto import MainScreenCategoryList
from src.domain.dto.service.user_history_dto import RequestSetUserHistoryDto
from src.domain.entities.merge_history_entity import MergeHistoryEntity
from src.domain.entities.user_history_entity import UserHistoryEntity
from src.infra.database.repository.merge_history_repository import MergeHistoryRepository
from src.infra.database.repository.user_history_repository import UserHistoryRepository
from src.logger.custom_logger import get_logger
from src.service.application.prompts import RESPONSE_MESSAGES
from src.service.application.utils import extract_tags_by_category, format_collected_data_for_server, \
    validate_user_input, build_tags_progress_message, remove_tag_from_session, clear_tags_for_category

logger = get_logger(__name__)

TAG_ACTION_PREFIX = "__TAG_ACTION__:"
TAG_ACTION_SEPARATOR = "::"
TAG_ACTION_REMOVE = "remove"
TAG_ACTION_CLEAR = "clear"


def _parse_tag_action(user_response: str):
    """
    태그 관련 사용자 액션 파싱

    형식: "__TAG_ACTION__:<action>::<category>::<tag>"
    - action: remove | clear
    - category: 카테고리명
    - tag: 제거할 태그 (clear의 경우 생략 가능)
    """
    if not user_response or not user_response.startswith(TAG_ACTION_PREFIX):
        return None

    payload = user_response[len(TAG_ACTION_PREFIX):]
    parts = payload.split(TAG_ACTION_SEPARATOR, 2)

    if not parts or len(parts) < 2:
        return None

    action = parts[0].strip().lower()
    category = parts[1].strip()
    target_tag = parts[2].strip() if len(parts) > 2 else ""

    return action, category, target_tag


def _get_current_category(session: Dict) -> str:
    selected_categories = session.get("selectedCategories", [])
    current_index = session.get("currentCategoryIndex", 0)

    if 0 <= current_index < len(selected_categories):
        return selected_categories[current_index]
    return None


def _build_progress(session: Dict) -> Dict[str, int]:
    selected_categories = session.get("selectedCategories", [])
    current_index = session.get("currentCategoryIndex", 0)
    if not selected_categories:
        return None
    return {
        "current": current_index,
        "total": len(selected_categories)
    }


def _handle_tag_clear(session: Dict, category: str) -> ResponseChatServiceDTO:
    clear_tags_for_category(session, category)
    session["waitingForUserAction"] = False

    cleared_message = RESPONSE_MESSAGES["tags"]["cleared"]
    reask_template = RESPONSE_MESSAGES["start"]["reask_category"]
    message = f"{cleared_message}\n\n{reask_template.format(current_category=category)}"

    return ResponseChatServiceDTO(
        status="success",
        message=message,
        stage="collecting_details",
        tags=[],
        progress=_build_progress(session),
        showYesNoButtons=False,
        currentCategory=category
    )


def _handle_tag_remove(session: Dict, category: str, target_tag: str) -> ResponseChatServiceDTO:
    collected_tags = session.setdefault("collectedTags", {})
    existing_tags = collected_tags.get(category, [])

    if not existing_tags or target_tag not in existing_tags:
        not_found_message = RESPONSE_MESSAGES["tags"].get("not_found", "삭제할 태그를 찾지 못했어.")
        current_message = build_tags_progress_message(existing_tags) if existing_tags else ""
        combined_message = not_found_message if not current_message else f"{not_found_message}\n\n{current_message}"

        session["waitingForUserAction"] = bool(existing_tags)

        return ResponseChatServiceDTO(
            status="success",
            message=combined_message,
            stage="collecting_details",
            tags=existing_tags or None,
            progress=_build_progress(session),
            showYesNoButtons=bool(existing_tags),
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["yes_no_question"] if existing_tags else None,
            currentCategory=category
        )

    updated_tags = remove_tag_from_session(session, category, target_tag)

    if updated_tags:
        removed_message = RESPONSE_MESSAGES["tags"]["removed"].format(removed_tag=target_tag)
        current_message = build_tags_progress_message(updated_tags)
        combined_message = f"{removed_message}\n\n{current_message}"

        session["waitingForUserAction"] = True

        return ResponseChatServiceDTO(
            status="success",
            message=combined_message,
            stage="collecting_details",
            tags=updated_tags,
            progress=_build_progress(session),
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["yes_no_question"],
            currentCategory=category
        )

    # 모든 태그가 삭제된 경우
    removed_message = RESPONSE_MESSAGES["tags"]["removed"].format(removed_tag=target_tag)
    session["waitingForUserAction"] = False

    reask_template = RESPONSE_MESSAGES["start"]["reask_category"]
    message = f"{removed_message}\n\n{RESPONSE_MESSAGES['tags']['cleared']}\n\n{reask_template.format(current_category=category)}"

    return ResponseChatServiceDTO(
        status="success",
        message=message,
        stage="collecting_details",
        tags=[],
        progress=_build_progress(session),
        showYesNoButtons=False,
        currentCategory=category
    )


def _handle_tag_action(session: Dict, user_response: str) -> ResponseChatServiceDTO:
    parsed = _parse_tag_action(user_response)

    if not parsed:
        return None

    action, category, target_tag = parsed
    current_category = _get_current_category(session)

    # 현재 카테고리가 없거나 생략된 경우 현재 카테고리로 보정
    if not category:
        category = current_category

    if not category:
        # 카테고리를 식별할 수 없는 예외 상황
        message = RESPONSE_MESSAGES["validation"]["ambiguous"]
        session["waitingForUserAction"] = False
        return ResponseChatServiceDTO(
            status="validation_failed",
            message=message,
            stage="collecting_details",
        )

    if action == TAG_ACTION_CLEAR:
        return _handle_tag_clear(session, category)
    elif action == TAG_ACTION_REMOVE:
        return _handle_tag_remove(session, category, target_tag)

    return None


async def get_store_recommendations(session: Dict) -> Dict[str, List[MainScreenCategoryList]]:
    """
    세션의 collectedData를 기반으로 매장 추천
    """
    from src.service.suggest.store_suggest_service import StoreSuggestService
    from src.infra.external.query_enchantment import QueryEnhancementService

    logger.info("=" * 60)
    logger.info("매장 추천 시작")
    logger.info("=" * 60)

    suggest_service = StoreSuggestService()
    query_enhancer = QueryEnhancementService()
    recommendations = {}

    # 지역/인원/수집된 태그
    region = extract_region_from_address(session.get("play_address", ""))
    people_count = session.get("peopleCount", 1)
    collected_tags = session.get("collectedTags", {})
    selected_categories = session.get("selectedCategories", [])
    categories_to_process = selected_categories or list(collected_tags.keys())
    random_categories = set(session.get("randomCategories", []))

    logger.info(f"지역: {region}")
    logger.info(f"인원: {people_count}명")
    logger.info(f"수집된 태그: {collected_tags}")
    logger.info(f"랜덤 카테고리: {random_categories}")

    for category in categories_to_process:
        keywords = collected_tags.get(category, [])
        keyword_string = ", ".join(keywords) if keywords else ""
        
        # 🔥 랜덤 추천 여부 확인
        is_random = category in random_categories

        logger.info(f"[{category}] 키워드: {keyword_string if keyword_string else '(없음 - 랜덤 추천)'}")

        try:
            # 🔥 랜덤인 경우: DB에서 직접 조회
            if is_random:
                logger.info(f"[{category}] 랜덤 추천 모드 - DB에서 직접 조회")
                
                stores_as_dicts = await suggest_service.get_random_stores_from_db(
                    region=region,
                    category_type=category,
                    n_results=10
                )
                
                logger.info(f"[{category}] DB 랜덤 조회 결과: {len(stores_as_dicts)}개")
                
                # dict -> MainScreenCategoryList 변환
                filtered_list = []
                for store in stores_as_dicts:
                    filtered_list.append(
                        MainScreenCategoryList(
                            id=store.get('id', ''),
                            title=store.get('title', ''),
                            image_url=store.get('image_url', ''),
                            detail_address=store.get('detail_address', ''),
                            sub_category=store.get('sub_category', ''),
                            lat=store.get('lat'),
                            lng=store.get('lng')
                        )
                    )
                
                recommendations[category] = filtered_list
                logger.info(f"[{category}] 랜덤 추천 완료: {len(filtered_list)}개")
                
            else:
                # 🔥 일반 추천: ChromaDB + GPT 필터링
                logger.info(f"[{category}] 일반 추천 모드 - ChromaDB 검색")
                
                suggestions = await suggest_service.suggest_stores(
                    personnel=people_count,
                    region=region,
                    category_type=category,
                    user_keyword=keyword_string,
                    n_results=15,
                    use_ai_enhancement=False,
                    min_similarity_threshold=0.2,
                    rerank_candidates_multiplier=5,
                    keyword_weight=0.5,
                    semantic_weight=0.3,
                    rerank_weight=0.2
                )

                logger.info(f"[{category}] ChromaDB 검색 결과: {len(suggestions)}개")

                store_ids = [sug.get('store_id') for sug in suggestions if sug.get('store_id')]

                if store_ids:
                    store_details = await suggest_service.get_store_details(store_ids)

                    # MainScreenCategoryList 형식으로 변환
                    stores_as_dicts = []
                    for store in store_details:
                        address = (
                            (store.get('do', '') + " " if store.get('do') else "") +
                            (store.get('si', '') + " " if store.get('si') else "") +
                            (store.get('gu', '') + " " if store.get('gu') else "") +
                            (store.get('detail_address', '') if store.get('detail_address') else "")
                        ).strip()

                        stores_as_dicts.append({
                            'id': store.get('id', ''),
                            'title': store.get('name', ''),
                            'image_url': store.get('image', ''),
                            'detail_address': address,
                            'sub_category': store.get('sub_category', ''),
                            'business_hour': store.get('business_hour', ''),
                            'phone': store.get('phone', ''),
                            'menu': store.get('menu', '') or '정보없음',
                            'lat': str(store.get('latitude', '')) if store.get('latitude') else None,
                            'lng': str(store.get('longitude', '')) if store.get('longitude') else None,
                        })

                    logger.info(f"[{category}] 후보 매장 상세 조회 완료: {len(stores_as_dicts)}개")

                    # GPT-4.1 필터링
                    filtered_dicts = await query_enhancer.filter_recommendations_with_gpt(
                        stores=stores_as_dicts,
                        user_keywords=keywords,
                        category_type=category,
                        personnel=people_count,
                        max_results=10,
                        fill_with_original=False
                    )

                    # dict -> MainScreenCategoryList 변환
                    filtered_list = []
                    for store in filtered_dicts:
                        filtered_list.append(
                            MainScreenCategoryList(
                                id=store.get('id', ''),
                                title=store.get('title', ''),
                                image_url=store.get('image_url', ''),
                                detail_address=store.get('detail_address', ''),
                                sub_category=store.get('sub_category', ''),
                                lat=store.get('lat'),
                                lng=store.get('lng')
                            )
                        )

                    recommendations[category] = filtered_list
                    logger.info(f"[{category}] GPT 필터링 완료: {len(filtered_list)}개")

                else:
                    recommendations[category] = []
                    logger.warning(f"[{category}] 추천 후보 없음")

        except Exception as e:
            logger.error(f"[{category}] 추천 중 오류: {e}")
            recommendations[category] = []

    logger.info(f"전체 추천 완료: {sum(len(v) for v in recommendations.values())}개 매장")
    logger.info("=" * 60)
    return recommendations


def extract_region_from_address(address: str) -> str:
    """
    주소에서 구 단위 추출
    예: "서울시 강남구 역삼동" -> "강남구"
    """
    if not address:
        return None
    parts = address.split()
    for part in parts:
        if part.endswith("구"):
            return part
    return None


def handle_user_message(session: Dict, user_message: str) -> ResponseChatServiceDTO:
    """
    사용자 메시지 처리 및 태그 생성
    """
    session["conversationHistory"].append({
        "role": "user",
        "message": user_message
    })
    session["lastUserMessage"] = user_message

    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]

    if current_index >= len(selected_categories):
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True
        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
            availableCategories=selected_categories
        )

    current_category = selected_categories[current_index]
    people_count = session.get("peopleCount", 1)

    # 🔥 LLM으로 검증 + 랜덤 판별 (1회 호출)
    result_type, error_message = validate_user_input(user_message, current_category)

    # 🔥 Case 1: 랜덤 추천 요청
    if result_type == "random":
        logger.info(f"LLM 판단: 랜덤 추천 요청 - '{user_message}'")
        
        session.setdefault("collectedTags", {})
        session.setdefault("randomCategories", [])
        session["randomCategoryPending"] = current_category
        session["stage"] = "confirming_random"
        session["waitingForUserAction"] = True

        progress = {
            "current": current_index,
            "total": len(selected_categories)
        }

        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["random"]["ask"],
            stage="confirming_random",
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["random"]["ask_question"],
            currentCategory=current_category,
            progress=progress
        )

    # 🔥 Case 2: 의미없는 입력
    if result_type == "invalid":
        logger.warning(f"LLM 판단: 의미없는 입력 - '{user_message}'")
        return ResponseChatServiceDTO(
            status="validation_failed",
            message=error_message,
            stage="collecting_details",
            currentCategory=current_category
        )

    # 🔥 Case 3: 의미있는 입력 → 태그 추출
    logger.info(f"LLM 판단: 의미있는 입력 - '{user_message}'")
    
    new_tags = extract_tags_by_category(user_message, current_category, people_count)

    if "collectedTags" not in session:
        session["collectedTags"] = {}

    if current_category in session["collectedTags"]:
        existing_tags = session["collectedTags"][current_category]
        combined_tags = existing_tags + new_tags
        combined_tags = list(dict.fromkeys(combined_tags))
        session["collectedTags"][current_category] = combined_tags
        session["pendingTags"] = combined_tags
    else:
        session["collectedTags"][current_category] = new_tags
        session["pendingTags"] = new_tags

    tags = session["pendingTags"]
    message = build_tags_progress_message(tags)

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
        showYesNoButtons=True,
        yesNoQuestion="이 정보로 다음 질문으로 넘어갈래?",
        currentCategory=current_category
    )


async def handle_user_action_response(session: Dict, user_response: str) -> ResponseChatServiceDTO:
    """
    사용자 버튼 액션 처리 (Next / More / Yes)
    """
    tag_action_response = _handle_tag_action(session, user_response)
    if tag_action_response:
        return tag_action_response

    is_next = any(word in user_response.lower() for word in
                  ["yes", "응", "고", "네", "넵", "예", "좋아", "좋아요", "그래", "맞아", "ㅇㅇ", "기기", "ㄱㄱ", "고고", "네네", "다음", "다음 질문", "다음질문"])
    is_more = any(word in user_response.lower() for word in ["추가", "더", "더해", "추가하기", "추가요", "더할래"])

    if session.get("stage") == "confirming_random":
        pending_category = session.get("randomCategoryPending")

        if not pending_category:
            session["stage"] = "collecting_details"
            session["waitingForUserAction"] = False
            return ResponseChatServiceDTO(
                status="success",
                message=RESPONSE_MESSAGES["start"]["unclear_response"],
                stage="collecting_details",
                showYesNoButtons=True,
                yesNoQuestion=RESPONSE_MESSAGES["buttons"]["yes_no_question"]
            )

        if is_next:
            random_categories = session.setdefault("randomCategories", [])
            if pending_category not in random_categories:
                random_categories.append(pending_category)

            collected_tags = session.setdefault("collectedTags", {})
            collected_tags.setdefault(pending_category, [])

            session["randomCategoryPending"] = None
            session["waitingForUserAction"] = False
            session["stage"] = "collecting_details"

            next_response = handle_next_category(session)
            ready_message = RESPONSE_MESSAGES["random"]["ready"]

            if next_response.message:
                next_response.message = f"{ready_message}\n\n{next_response.message}"
            else:
                next_response.message = ready_message

            session["stage"] = next_response.stage
            return next_response
        else:
            session["randomCategoryPending"] = None
            session["waitingForUserAction"] = False
            session["stage"] = "collecting_details"

            current_index = session.get("currentCategoryIndex", 0)
            selected_categories = session.get("selectedCategories", [])
            current_category = selected_categories[current_index] if current_index < len(selected_categories) else pending_category

            progress = {
                "current": current_index,
                "total": len(selected_categories)
            } if current_category and selected_categories else None

            return ResponseChatServiceDTO(
                status="success",
                message=RESPONSE_MESSAGES["random"]["decline"],
                stage="collecting_details",
                currentCategory=current_category,
                progress=progress,
                showYesNoButtons=False
            )

    # 🔥 결과 출력 확인 단계: Yes(매장 추천 생성)
    if session.get("stage") == "confirming_results":
        if is_next:
            logger.info("confirming_results 단계에서 '네' 선택 -> 매장 추천 생성 (GPT 필터링)")
            
            # 수집된 데이터 구조화
            collected_data = format_collected_data_for_server(session)
            
            # 🔥 매장 추천 생성 (ChromaDB + GPT-4.1 필터링)
            recommendations = await get_store_recommendations(session)
            
            # 세션에 저장
            session["recommendations"] = recommendations
            session["stage"] = "completed"
            session["waitingForUserAction"] = False

            return ResponseChatServiceDTO(
                status="success",
                message=RESPONSE_MESSAGES["start"]["final_result"],
                stage="completed",
                recommendations=recommendations,
                collectedData=collected_data
            )
        else:
            return ResponseChatServiceDTO(
                status="success",
                message=RESPONSE_MESSAGES["start"]["unclear_result_response"],
                stage="confirming_results",
                showYesNoButtons=True,
                yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"]
            )

    # 태그 수집 단계
    if is_next and not is_more:
        return handle_next_category(session)
    elif is_more and not is_next:
        return handle_add_more_tags(session)
    else:
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
    """
    session["waitingForUserAction"] = False

    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]

    if current_index >= len(selected_categories):
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True
        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
            availableCategories=selected_categories
        )

    session["currentCategoryIndex"] += 1

    if session["currentCategoryIndex"] < len(selected_categories):
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
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True

        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,
            yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
            availableCategories=selected_categories
        )


def handle_modification_mode(session: Dict, user_message: str) -> ResponseChatServiceDTO:
    """
    수정 모드 처리 (현재 미사용)
    """
    pass


def handle_add_more_tags(session: Dict) -> ResponseChatServiceDTO:
    """
    More 버튼 처리
    """
    session["waitingForUserAction"] = False

    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]

    if current_index >= len(selected_categories):
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True
        return ResponseChatServiceDTO(
            status="success",
            message=RESPONSE_MESSAGES["start"]["all_completed"],
            stage="confirming_results",
            showYesNoButtons=True,
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


#   일정표 저장
async def save_selected_template_to_merge(dto: RequestSetUserHistoryDto, user_id: str) -> str:
    logger.info(f"try to merge history: {user_id}")

    try:
        if dto.template_type == "0":
            name = ", ".join([i.category_name for i in dto.category])
        else:
            name = "→".join([i.category_name for i in dto.category])

        repo = MergeHistoryRepository()

        entity = MergeHistoryEntity.from_dto(
            user_id=user_id,
            categories_name=name,
            template_type=dto.template_type,
        )
        print(f"entity : {entity}")

        await repo.insert(entity)


    except Exception as e:
        logger.error(f"error insert history {e}")
        print(dto)
        raise Exception(e)

    logger.info(f"Inserting history successes: {dto}")
    return entity.id



async def save_selected_template(dto: RequestSetUserHistoryDto, merge_id: str, user_id: str):
    logger.info(f"try to save history: {user_id}")

    try:
        repo = UserHistoryRepository()

        for i in range(len(dto.category)):
            entity = UserHistoryEntity.from_dto(
                user_id=user_id,
                seq=i,
                merge_id=merge_id,
                **dto.category[i].model_dump()
            )
            await repo.insert(entity)

    except Exception as e:
        logger.error(f"error insert history {e}")
        raise Exception(e)

    logger.info(f"Inserting history successes: {dto}")
    return True