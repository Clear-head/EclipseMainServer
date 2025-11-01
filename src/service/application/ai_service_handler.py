"""
대화 흐름 제어 핸들러
"""

from typing import Dict, List

from src.domain.dto.service.haru_service_dto import ResponseChatServiceDTO
from src.domain.dto.service.main_screen_dto import MainScreenCategoryList
from src.service.application.prompts import RESPONSE_MESSAGES
from src.service.application.utils import extract_tags_by_category, format_collected_data_for_server
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


async def get_store_recommendations(session: Dict) -> Dict[str, List[MainScreenCategoryList]]:
    """
    세션의 collectedData를 기반으로 매장 추천 (GPT-4.1 필터링 적용)
    
    Args:
        session: 세션 데이터 (collectedTags, play_address, peopleCount 포함)
    
    Returns:
        카테고리별 추천 매장 딕셔너리 (MainScreenCategoryList 형식)
    """
    from src.service.suggest.store_suggest_service import StoreSuggestService
    from src.infra.external.query_enchantment import QueryEnhancementService
    
    logger.info("=" * 60)
    logger.info("매장 추천 시작 (GPT-4.1 필터링 적용)")
    
    suggest_service = StoreSuggestService()
    query_enhancer = QueryEnhancementService()
    recommendations = {}
    
    # 지역 추출
    region = extract_region_from_address(session.get("play_address", ""))
    people_count = session.get("peopleCount", 1)
    collected_tags = session.get("collectedTags", {})
    
    logger.info(f"지역: {region}")
    logger.info(f"인원: {people_count}명")
    logger.info(f"수집된 태그: {collected_tags}")
    
    # 각 카테고리별로 매장 추천
    for category, keywords in collected_tags.items():
        keyword_string = ", ".join(keywords) if keywords else ""
        
        logger.info(f"[{category}] 키워드: {keyword_string}")
        
        try:
            # 1단계: ChromaDB 하이브리드 검색 (더 많이 가져오기)
            suggestions = await suggest_service.suggest_stores(
                personnel=people_count,
                region=region,
                category_type=category,
                user_keyword=keyword_string,
                n_results=15,  # 🔥 15개 가져와서 GPT가 8개 선택
                use_ai_enhancement=False,
                min_similarity_threshold=0.70  # 🔥 임계값 낮춤 (더 많은 후보)
            )
            
            logger.info(f"[{category}] ChromaDB 검색 결과: {len(suggestions)}개")
            
            # store_id 추출
            store_ids = [sug.get('store_id') for sug in suggestions if sug.get('store_id')]
            
            # 상세 정보 조회
            if store_ids:
                store_details = await suggest_service.get_store_details(store_ids)
                
                # MainScreenCategoryList 형식으로 변환
                category_list = []
                for store in store_details:
                    address = (
                        (store.get('do', '') + " " if store.get('do') else "") +
                        (store.get('si', '') + " " if store.get('si') else "") +
                        (store.get('gu', '') + " " if store.get('gu') else "") +
                        (store.get('detail_address', '') if store.get('detail_address') else "")
                    ).strip()
                    
                    category_list.append(
                        MainScreenCategoryList(
                            id=store.get('id', ''),
                            title=store.get('name', ''),
                            image_url=store.get('image', ''),
                            detail_address=address,
                            sub_category=store.get('sub_category', '')
                        )
                    )
                
                logger.info(f"[{category}] 변환 완료: {len(category_list)}개")
                
                # 🔥 2단계: GPT-4.1 필터링 (15개 → 8개 선택)
                if len(category_list) > 8:
                    logger.info(f"[{category}] GPT-4.1 필터링 시작...")
                    
                    # MainScreenCategoryList를 dict로 변환
                    stores_as_dicts = [
                        {
                            'id': store.id,
                            'title': store.title,
                            'image_url': store.image_url,
                            'detail_address': store.detail_address,
                            'sub_category': store.sub_category
                        }
                        for store in category_list
                    ]
                    
                    filtered_dicts = await query_enhancer.filter_recommendations_with_gpt(
                        stores=stores_as_dicts,
                        user_keywords=keywords,
                        category_type=category,
                        personnel=people_count,
                        max_results=8
                    )
                    
                    # dict를 다시 MainScreenCategoryList로 변환
                    filtered_list = [
                        MainScreenCategoryList(
                            id=store['id'],
                            title=store['title'],
                            image_url=store['image_url'],
                            detail_address=store['detail_address'],
                            sub_category=store['sub_category']
                        )
                        for store in filtered_dicts
                    ]
                    
                    recommendations[category] = filtered_list
                    logger.info(f"[{category}] GPT 필터링 완료: {len(filtered_list)}개")
                else:
                    # 8개 이하면 필터링 없이 그대로 사용
                    recommendations[category] = category_list
                    logger.info(f"[{category}] 8개 이하라서 필터링 생략")
            else:
                recommendations[category] = []
                logger.warning(f"[{category}] 추천 결과 없음")
                
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
    message = f"현재까지 수집된 키워드: {', '.join(tags)}"

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
        yesNoQuestion="이 정보로 다음 질문으로 넘어가시겠습니까?",
        currentCategory=current_category
    )


async def handle_user_action_response(session: Dict, user_response: str) -> ResponseChatServiceDTO:
    """
    사용자 버튼 액션 처리 (Next / More / Yes)
    """
    is_next = any(word in user_response.lower() for word in
                  ["yes", "네", "넵", "예", "좋아", "좋아요", "그래", "맞아", "ㅇㅇ", "기기", "ㄱㄱ", "고고", "네네", "다음"])
    is_more = any(word in user_response.lower() for word in ["추가", "더", "더해", "추가하기", "추가요", "더할래"])

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