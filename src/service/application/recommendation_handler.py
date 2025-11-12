"""
매장 추천 기능 처리 모듈
- ChromaDB 검색 기반 추천
- GPT 필터링 추천
- 랜덤 추천
- 추천 결과 포맷팅
"""

from typing import Dict, List, Optional

from src.domain.dto.category.category_dto import CategoryListItemDTO
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)

# ==================== 추천 시스템 설정 ====================
RECOMMENDATION_CONFIG = {
    "chromadb_results": 15,
    "gpt_max_results": 10,
    "random_results": 10,
    "min_similarity": 0.2,
    "rerank_multiplier": 5,
    "keyword_weight": 0.5,
    "semantic_weight": 0.3,
    "rerank_weight": 0.2
}

def format_store_address(store: Dict) -> str:
    """매장 주소 포맷팅"""
    address_parts = [
        store.get('do', ''),
        store.get('si', ''),
        store.get('gu', ''),
        store.get('detail_address', '')
    ]
    return " ".join(part for part in address_parts if part).strip()


# ==================== DTO 변환 ====================
def convert_stores_to_dto(stores: List[Dict]) -> List[CategoryListItemDTO]:
    """매장 dict 리스트를 DTO 리스트로 변환"""
    return [
        CategoryListItemDTO(
            id=store.get('id', ''),
            title=store.get('title', ''),
            image_url=store.get('image_url', ''),
            detail_address=store.get('detail_address', ''),
            sub_category=store.get('sub_category', ''),
            lat=store.get('lat'),
            lng=store.get('lng')
        )
        for store in stores
    ]


def prepare_store_details(store_details: List[Dict]) -> List[Dict]:
    """매장 상세 정보를 GPT 필터링용 형식으로 변환"""
    stores_as_dicts = []
    
    for store in store_details:
        stores_as_dicts.append({
            'id': store.get('id', ''),
            'title': store.get('name', ''),
            'image_url': store.get('image', ''),
            'detail_address': format_store_address(store),
            'sub_category': store.get('sub_category', ''),
            'business_hour': store.get('business_hour', ''),
            'phone': store.get('phone', ''),
            'menu': store.get('menu', '') or '정보없음',
            'lat': str(store.get('latitude', '')) if store.get('latitude') else None,
            'lng': str(store.get('longitude', '')) if store.get('longitude') else None,
        })
    
    return stores_as_dicts


# ==================== 랜덤 추천 ====================
async def get_random_recommendations(
    suggest_service,
    region: str,
    category: str
) -> List[CategoryListItemDTO]:
    """
    랜덤 추천 조회
    
    Args:
        suggest_service: 추천 서비스 인스턴스
        region: 지역 (구 단위)
        category: 카테고리명
    """
    logger.info(f"[{category}] 랜덤 추천 모드 - DB에서 직접 조회")
    
    stores_as_dicts = await suggest_service.get_random_stores_from_db(
        region=region,
        category_type=category,
        n_results=RECOMMENDATION_CONFIG["random_results"]
    )
    
    logger.info(f"[{category}] DB 랜덤 조회 결과: {len(stores_as_dicts)}개")
    return convert_stores_to_dto(stores_as_dicts)


# ==================== 일반 추천 (ChromaDB + GPT) ====================
async def get_filtered_recommendations(
    suggest_service,
    query_enhancer,
    region: str,
    category: str,
    keywords: List[str],
    people_count: int
) -> List[CategoryListItemDTO]:
    """
    일반 추천 (ChromaDB + GPT 필터링)
    
    Args:
        suggest_service: 추천 서비스 인스턴스
        query_enhancer: 쿼리 향상 서비스 인스턴스
        region: 지역 (구 단위)
        category: 카테고리명
        keywords: 사용자 키워드 리스트
        people_count: 인원 수
    """
    logger.info(f"[{category}] 일반 추천 모드 - ChromaDB 검색")
    
    keyword_string = ", ".join(keywords)
    
    # ChromaDB 검색
    suggestions = await suggest_service.suggest_stores(
        personnel=people_count,
        region=region,
        category_type=category,
        user_keyword=keyword_string,
        n_results=RECOMMENDATION_CONFIG["chromadb_results"],
        use_ai_enhancement=False,
        min_similarity_threshold=RECOMMENDATION_CONFIG["min_similarity"],
        rerank_candidates_multiplier=RECOMMENDATION_CONFIG["rerank_multiplier"],
        keyword_weight=RECOMMENDATION_CONFIG["keyword_weight"],
        semantic_weight=RECOMMENDATION_CONFIG["semantic_weight"],
        rerank_weight=RECOMMENDATION_CONFIG["rerank_weight"]
    )

    logger.info(f"[{category}] ChromaDB 검색 결과: {len(suggestions)}개")

    store_ids = [sug.get('store_id') for sug in suggestions if sug.get('store_id')]
    
    if not store_ids:
        logger.warning(f"[{category}] 추천 후보 없음")
        return []

    # 매장 상세 정보 조회
    store_details = await suggest_service.get_store_details(store_ids)
    stores_as_dicts = prepare_store_details(store_details)
    
    logger.info(f"[{category}] 후보 매장 상세 조회 완료: {len(stores_as_dicts)}개")

    # GPT 필터링
    filtered_dicts = await query_enhancer.filter_recommendations_with_gpt(
        stores=stores_as_dicts,
        user_keywords=keywords,
        category_type=category,
        personnel=people_count,
        max_results=RECOMMENDATION_CONFIG["gpt_max_results"],
        fill_with_original=False
    )

    logger.info(f"[{category}] GPT 필터링 완료: {len(filtered_dicts)}개")
    return convert_stores_to_dto(filtered_dicts)


# ==================== 통합 추천 ====================
async def get_store_recommendations(session: Dict) -> Dict[str, List[CategoryListItemDTO]]:
    """
    세션 데이터를 기반으로 매장 추천
    
    Args:
        session: 현재 세션 (collectedTags, selectedCategories 등 포함)
        
    Returns:
        카테고리별 추천 매장 딕셔너리
    """
    from src.service.suggest.store_suggest_service import StoreSuggestService
    from src.infra.external.query_enchantment import QueryEnhancementService

    logger.info("=" * 60)
    logger.info("매장 추천 시작")
    logger.info("=" * 60)

    suggest_service = StoreSuggestService()
    query_enhancer = QueryEnhancementService()
    recommendations = {}

    # 세션 데이터 추출
    region = session.get("play_address", "")
    people_count = session.get("peopleCount", 1)
    collected_tags = session.get("collectedTags", {})
    selected_categories = session.get("selectedCategories", [])
    categories_to_process = selected_categories or list(collected_tags.keys())
    random_categories = set(session.get("randomCategories", []))

    logger.info(f"지역: {region}")
    logger.info(f"인원: {people_count}명")
    logger.info(f"수집된 태그: {collected_tags}")
    logger.info(f"랜덤 카테고리: {random_categories}")

    # 카테고리별 추천 처리
    for category in categories_to_process:
        keywords = collected_tags.get(category, [])
        is_random = category in random_categories

        keyword_display = ", ".join(keywords) if keywords else "(없음 - 랜덤 추천)"
        logger.info(f"[{category}] 키워드: {keyword_display}")

        try:
            if is_random:
                # 랜덤 추천
                recommendations[category] = await get_random_recommendations(
                    suggest_service, region, category
                )
            else:
                # 일반 추천 (ChromaDB + GPT)
                recommendations[category] = await get_filtered_recommendations(
                    suggest_service, query_enhancer, region, category, keywords, people_count
                )

        except Exception as e:
            logger.error(f"[{category}] 추천 중 오류: {e}", exc_info=True)
            recommendations[category] = []

    total_stores = sum(len(stores) for stores in recommendations.values())
    logger.info(f"전체 추천 완료: {total_stores}개 매장")
    logger.info("=" * 60)
    
    return recommendations