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
    validate_user_input

logger = get_logger(__name__)


CHOICE_AVOIDANCE_KEYWORDS = [
    "아무거나", "상관없어", "상관없어요", "다좋아", "다 좋아", "다 괜찮",
    "알아서", "맡길게", "편한대로", "편한 대로", "대충골라", "대충 골라",
    "적당히골라", "적당히 골라", "기대안할게", "기대 안할게", "기대안",
    "뭐든", "anything", "둘다좋아", "둘 다 좋아"
]


def is_choice_avoidance_message(message: str) -> bool:
    if not message:
        return False

    normalized = message.strip().lower().replace(" ", "")

    if "말고" in normalized or "싫" in normalized:
        return False

    return any(keyword in normalized for keyword in CHOICE_AVOIDANCE_KEYWORDS)


async def get_store_recommendations(session: Dict) -> Dict[str, List[MainScreenCategoryList]]:
    """
    세션의 collectedData를 기반으로 매장 추천 (GPT-4.1 필터링 적용, 부족 시 채우지 않음)
    """
    from src.service.suggest.store_suggest_service import StoreSuggestService
    from src.infra.external.query_enchantment import QueryEnhancementService

    logger.info("=" * 60)
    logger.info("매장 추천 시작 (GPT-4.1 필터링 적용: 부족분 채우지 않음)")
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
    random_mode = session.get("randomModeActive", False)

    logger.info(f"지역: {region}")
    logger.info(f"인원: {people_count}명")
    logger.info(f"수집된 태그: {collected_tags}")

    for category in categories_to_process:
        keywords = collected_tags.get(category, [])
        keyword_string = ", ".join(keywords) if keywords else ""

        logger.info(f"[{category}] 키워드: {keyword_string}")
        if random_mode and not keywords:
            logger.info(f"[{category}] 랜덤 추천 모드 - 키워드 없이 검색 진행")

        try:
            # 1단계: 후보 충분히 확보 (더 많은 후보 추출)
            suggestions = await suggest_service.suggest_stores(
                personnel=people_count,
                region=region,
                category_type=category,
                user_keyword=keyword_string,
                n_results=15,  # 후보를 많이 가져와서 GPT가 선별
                use_ai_enhancement=False,
                min_similarity_threshold=0.2,  # 후보 다양성 확보 (필요 시 조정)
                rerank_candidates_multiplier=5,
                keyword_weight=0.5,
                semantic_weight=0.3,
                rerank_weight=0.2
            )

            logger.info(f"[{category}] ChromaDB 검색 결과: {len(suggestions)}개")

            store_ids = [sug.get('store_id') for sug in suggestions if sug.get('store_id')]

            if store_ids:
                store_details = await suggest_service.get_store_details(store_ids)

                # ChromaDB 결과(점수 등)를 id->data 맵으로 보관
                id_to_chroma = {}
                for sug in suggestions:
                    sid = sug.get('store_id')
                    if sid:
                        id_to_chroma[sid] = {
                            'similarity_score': sug.get('similarity_score'),
                            'score_breakdown': sug.get('score_breakdown'),
                            'document': sug.get('document')
                        }

                # MainScreenCategoryList 형식으로 변환 (GPT 입력용 dict 리스트 생성)
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
                        'lat': str(store.get('latitude', '')) if store.get('latitude') else None,  # 🔥 추가
                        'lng': str(store.get('longitude', '')) if store.get('longitude') else None,  # 🔥 추가
                    })

                logger.info(f"[{category}] 후보 매장 상세 조회 및 변환 완료: {len(stores_as_dicts)}개")

                # 2단계: GPT-4.1 필터링 호출 (부족분 채우지 않음)
                filtered_dicts = await query_enhancer.filter_recommendations_with_gpt(
                    stores=stores_as_dicts,
                    user_keywords=keywords,
                    category_type=category,
                    personnel=people_count,
                    max_results=10,
                    fill_with_original=False  # 핵심: GPT가 적게 골랐다면 그 수만 반환
                )

                # dict -> MainScreenCategoryList 변환 및 recommendations 저장
                filtered_list = []
                for store in filtered_dicts:
                    filtered_list.append(
                        MainScreenCategoryList(
                            id=store.get('id', ''),
                            title=store.get('title', ''),
                            image_url=store.get('image_url', ''),
                            detail_address=store.get('detail_address', ''),
                            sub_category=store.get('sub_category', ''),
                            lat=store.get('lat'),  # 🔥 추가
                            lng=store.get('lng')   # 🔥 추가
                        )
                    )

                recommendations[category] = filtered_list
                logger.info(f"[{category}] 최종 추천 갯수: {len(filtered_list)}개")

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

    if is_choice_avoidance_message(user_message):
        session["randomModeRequested"] = True
        session["randomModeActive"] = False
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

    # ✅ 입력 검증 (하이브리드 방식)
    is_valid, error_message = validate_user_input(user_message, current_category)
    if not is_valid:
        logger.warning(f"입력 검증 실패: '{user_message}' -> {error_message}")
        return ResponseChatServiceDTO(
            status="validation_failed",
            message=error_message,
            stage="collecting_details",
            currentCategory=current_category
        )

    people_count = session.get("peopleCount", 1)
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
    message = f"현재까지 수집된 키워드\n: {', '.join(tags)}"

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
    is_next = any(word in user_response.lower() for word in
                  ["yes", "응", "고", "네", "넵", "예", "좋아", "좋아요", "그래", "맞아", "ㅇㅇ", "기기", "ㄱㄱ", "고고", "네네", "다음", "다음 질문", "다음질문"])
    is_more = any(word in user_response.lower() for word in ["추가", "더", "더해", "추가하기", "추가요", "더할래"])

    if session.get("stage") == "confirming_random":
        if is_next:
            selected_categories = session.get("selectedCategories", [])
            session["currentCategoryIndex"] = len(selected_categories)
            session["randomModeRequested"] = False
            session["randomModeActive"] = True
            session["waitingForUserAction"] = True
            session["stage"] = "confirming_results"

            collected_tags = session.setdefault("collectedTags", {})
            for category in selected_categories:
                collected_tags.setdefault(category, [])

            return ResponseChatServiceDTO(
                status="success",
                message=RESPONSE_MESSAGES["random"]["ready"],
                stage="confirming_results",
                showYesNoButtons=True,
                yesNoQuestion=RESPONSE_MESSAGES["buttons"]["result_question"],
                availableCategories=selected_categories
            )
        else:
            session["randomModeRequested"] = False
            session["randomModeActive"] = False
            session["waitingForUserAction"] = False

            current_index = session.get("currentCategoryIndex", 0)
            selected_categories = session.get("selectedCategories", [])
            current_category = selected_categories[current_index] if current_index < len(selected_categories) else None

            progress = None
            if current_category:
                progress = {
                    "current": current_index,
                    "total": len(selected_categories)
                }

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
            session["randomModeActive"] = False
            session["randomModeRequested"] = False
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