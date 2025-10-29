"""
ChromaDB 기반 매장 제안 서비스 (지역 필터링 개선)
"""
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

from src.logger.custom_logger import get_logger
from src.infra.external.query_enchantment import QueryEnhancementService

logger = get_logger(__name__)


class StoreSuggestService:
    """매장 제안 서비스 클래스"""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Args:
            persist_directory: ChromaDB 저장 경로
        """
        logger.info("매장 제안 서비스 초기화 중...")
        
        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 한국어 임베딩 모델 로드
        logger.info("한국어 임베딩 모델 로딩 중...")
        self.embedding_model = SentenceTransformer("jhgan/ko-sroberta-multitask")
        
        # 쿼리 개선 서비스 초기화
        self.query_enhancer = QueryEnhancementService()
        
        # 컬렉션 가져오기
        try:
            self.store_collection = self.client.get_collection(name="stores")
            logger.info(f"매장 컬렉션 로드 완료: {self.store_collection.count()}개 매장")
        except Exception as e:
            logger.error(f"매장 컬렉션을 찾을 수 없습니다: {e}")
            raise
    
    @staticmethod
    def convert_type_to_code(type_korean: str) -> str:
        """
        한글 타입을 코드로 변환
        
        Args:
            type_korean: 한글 타입 (음식점, 카페, 콘텐츠)
            
        Returns:
            str: 타입 코드 ("0", "1", "2")
        """
        type_map = {
            "음식점": "0",
            "카페": "1",
            "콘텐츠": "2"
        }
        return type_map.get(type_korean, "")
    
    async def suggest_stores(
        self,
        personnel: Optional[int] = None,
        region: Optional[str] = None,
        category_type: Optional[str] = None,
        user_keyword: str = "",
        n_results: int = 10,
        use_ai_enhancement: bool = True
    ) -> List[Dict]:
        """
        매장 제안
        
        Args:
            personnel: 인원 수 (1, 2, 3, 4, 5+)
            region: 지역 (구 단위, 예: "강남구")
            category_type: 카테고리 타입 ("음식점", "카페", "콘텐츠")
            user_keyword: 사용자 입력 키워드 (예: "조용한 분위기 좋은")
            n_results: 반환할 결과 수
            use_ai_enhancement: AI 쿼리 개선 사용 여부
            
        Returns:
            List[Dict]: 제안 매장 리스트
        """
        logger.info("=" * 60)
        logger.info("매장 제안 요청")
        logger.info(f"  - 인원: {personnel}명")
        logger.info(f"  - 지역: {region}")
        logger.info(f"  - 타입: {category_type}")
        logger.info(f"  - 원본 키워드: {user_keyword}")
        logger.info(f"  - AI 개선: {use_ai_enhancement}")
        logger.info("=" * 60)
        
        # 검색 쿼리 생성 (AI 개선 사용 여부에 따라)
        if use_ai_enhancement:
            search_query = await self.query_enhancer.enhance_query(
                personnel=personnel,
                category_type=category_type,
                user_keyword=user_keyword
            )
        else:
            # 기본 쿼리 생성
            search_query = self.query_enhancer._build_fallback_query(
                personnel=personnel,
                category_type=category_type,
                user_keyword=user_keyword
            )
        
        logger.info(f"최종 검색 쿼리: {search_query}")
        
        # 필터 조건 구성
        where_filter = {}
        
        if category_type:
            type_code = self.convert_type_to_code(category_type)
            if type_code:
                where_filter["type_code"] = type_code
        
        # 쿼리 임베딩
        query_embedding = self.embedding_model.encode(search_query)
        
        # 검색 실행 (지역 필터가 있으면 더 많이 가져오기)
        fetch_count = n_results * 5 if region else n_results
        
        try:
            results = self.store_collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=fetch_count,
                where=where_filter if where_filter else None,
                include=["metadatas", "documents", "distances"]
            )
            
            logger.info(f"ChromaDB 검색 결과: {len(results['ids'][0])}개")
            
        except Exception as e:
            logger.error(f"ChromaDB 검색 중 오류: {e}")
            return []
        
        # 결과가 없으면 빈 리스트 반환
        if not results['ids'][0]:
            logger.warning("검색 결과가 없습니다.")
            return []
        
        # 결과 포맷팅 및 지역 필터링
        suggestions = []
        
        for i in range(len(results['ids'][0])):
            metadata = results['metadatas'][0][i]
            document = results['documents'][0][i]
            distance = results['distances'][0][i]
            store_id = results['ids'][0][i]
            
            # 디버그: 문서 내용 로깅
            if i < 3:  # 처음 3개만 로깅
                logger.debug(f"문서 {i+1}:\n{document}")
            
            # 지역 필터링 (후처리)
            if region:
                # document에서 "지역: XX구" 형태로 파싱
                store_region = ""
                for line in document.split('\n'):
                    line = line.strip()
                    if line.startswith('지역:'):
                        store_region = line.replace('지역:', '').strip()
                        break
                
                logger.debug(f"매장 {store_id} - 추출된 지역: '{store_region}', 필터 지역: '{region}'")
                
                # 지역 매칭 (부분 문자열 포함)
                if not store_region or region not in store_region:
                    logger.debug(f"매장 {store_id} - 지역 필터링으로 제외됨")
                    continue
            
            # 유사도 점수 계산 (거리를 점수로 변환)
            similarity_score = max(0, 1 - distance)
            
            suggestion = {
                'store_id': store_id,
                'type': metadata.get('type'),
                'similarity_score': round(similarity_score, 4),
                'distance': round(distance, 4),
                'document': document,
                'search_query': search_query  # 개선된 쿼리도 포함
            }
            
            suggestions.append(suggestion)
            logger.debug(f"매장 {store_id} 추가됨 (유사도: {similarity_score})")
            
            # 필요한 개수만큼 채우면 종료
            if len(suggestions) >= n_results:
                break
        
        logger.info(f"최종 제안 결과: {len(suggestions)}개")
        
        return suggestions
    
    async def get_store_details(self, store_ids: List[str]) -> List[Dict]:
        """
        매장 ID 목록으로 상세 정보 조회
        
        Args:
            store_ids: 매장 ID 리스트
            
        Returns:
            List[Dict]: 매장 상세 정보
        """
        from src.infra.database.repository.category_repository import CategoryRepository
        
        category_repo = CategoryRepository()
        store_details = []
        
        for store_id in store_ids:
            try:
                stores = await category_repo.select_by(id=store_id)
                if stores and len(stores) > 0:
                    store = stores[0]
                    store_dict = {
                        'id': store.id,
                        'name': store.name,
                        'do': store.do,
                        'si': store.si,
                        'gu': store.gu,
                        'detail_address': store.detail_address,
                        'sub_category': store.sub_category,
                        'business_hour': store.business_hour,
                        'phone': store.phone,
                        'type': store.type,
                        'image': store.image,
                        'latitude': store.latitude,
                        'longitude': store.longitude,
                        'menu': store.menu
                    }
                    store_details.append(store_dict)
            except Exception as e:
                logger.error(f"매장 ID '{store_id}' 조회 중 오류: {e}")
                continue
        
        return store_details