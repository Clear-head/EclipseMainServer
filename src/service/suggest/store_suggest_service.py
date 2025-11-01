"""
개선된 매장 제안 서비스 (키워드 매칭 + 시맨틱 검색 하이브리드)
"""
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer, CrossEncoder
import torch
import re
from collections import Counter

from src.infra.external.query_enchantment import QueryEnhancementService
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


class StoreSuggestService:
    """개선된 매장 제안 서비스 (키워드 매칭 중심)"""
    
    def __init__(self, persist_directory: str = "./chroma_db", use_reranker: bool = True):
        """
        Args:
            persist_directory: ChromaDB 저장 경로
            use_reranker: Re-ranking 모델 사용 여부
        """
        logger.info("개선된 매장 제안 서비스 초기화 중...")
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"사용 중인 디바이스: {self.device}")
        
        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 임베딩 모델 로드
        logger.info("임베딩 모델 로딩 중: intfloat/multilingual-e5-large")
        self.embedding_model = SentenceTransformer(
            "intfloat/multilingual-e5-large",
            device=self.device
        )
        logger.info(f"임베딩 모델 로딩 완료")
        
        # Re-ranking 모델 로드 (한국어 특화)
        self.use_reranker = use_reranker
        self.reranker = None
        
        if self.use_reranker:
            try:
                logger.info("Re-ranking 모델 로딩 중: BAAI/bge-reranker-base")
                self.reranker = CrossEncoder(
                    'BAAI/bge-reranker-base',
                    max_length=512,
                    device=self.device
                )
                logger.info(f"Re-ranking 모델 로딩 완료")
            except Exception as e:
                logger.error(f"Re-ranking 모델 로딩 실패: {e}")
                self.use_reranker = False
        
        self.query_enhancer = QueryEnhancementService()
        
        try:
            self.store_collection = self.client.get_collection(name="stores")
            logger.info(f"매장 컬렉션 로드 완료: {self.store_collection.count()}개 매장")
        except Exception as e:
            logger.error(f"매장 컬렉션을 찾을 수 없습니다: {e}")
            raise
    
    @staticmethod
    def convert_type_to_code(type_korean: str) -> str:
        """한글 타입을 코드로 변환"""
        type_map = {"음식점": "0", "카페": "1", "콘텐츠": "2"}
        return type_map.get(type_korean, "")
    
    def extract_keywords(self, text: str) -> List[str]:
        """텍스트에서 키워드 추출 (쉼표, 공백 기준)"""
        # 쉼표와 공백으로 분리
        keywords = re.split(r'[,\s]+', text)
        # 빈 문자열 제거 및 소문자 변환
        keywords = [k.strip() for k in keywords if k.strip()]
        return keywords
    
    def calculate_keyword_score(self, query_keywords: List[str], document: str) -> float:
        """
        키워드 매칭 점수 계산 (BM25 스타일)
        
        Args:
            query_keywords: 검색 키워드 리스트
            document: 문서 텍스트
            
        Returns:
            float: 키워드 매칭 점수 (0~1)
        """
        if not query_keywords:
            return 0.0
        
        doc_lower = document.lower()
        
        # 각 키워드가 문서에 등장하는지 확인
        matches = 0
        total_occurrences = 0
        
        for keyword in query_keywords:
            keyword_lower = keyword.lower()
            count = doc_lower.count(keyword_lower)
            if count > 0:
                matches += 1
                total_occurrences += count
        
        # 매칭 비율 계산
        match_ratio = matches / len(query_keywords)
        
        # 빈도 점수 (로그 스케일)
        import math
        frequency_score = math.log1p(total_occurrences) / 5.0  # 정규화
        
        # 최종 점수: 매칭 비율 70% + 빈도 30%
        final_score = (match_ratio * 0.7) + (min(frequency_score, 1.0) * 0.3)
        
        return final_score
    
    def hybrid_rerank(
        self,
        search_query: str,
        query_keywords: List[str],
        ids: List[str],
        metadatas: List[Dict],
        documents: List[str],
        distances: List[float],
        keyword_weight: float = 0.5,
        semantic_weight: float = 0.3,
        rerank_weight: float = 0.2
    ) -> List[tuple]:
        """
        하이브리드 Re-ranking: 키워드 + 시맨틱 + Cross-Encoder
        
        Args:
            search_query: 검색 쿼리
            query_keywords: 검색 키워드 리스트
            ids: 매장 ID 리스트
            metadatas: 메타데이터 리스트
            documents: 문서 리스트
            distances: 거리 리스트
            keyword_weight: 키워드 매칭 가중치 (기본 50%)
            semantic_weight: 시맨틱 유사도 가중치 (기본 30%)
            rerank_weight: Re-ranker 가중치 (기본 20%)
            
        Returns:
            List[tuple]: (id, metadata, document, final_score, score_details) 형태
        """
        logger.info(f"하이브리드 Re-ranking 시작: {len(ids)}개 문서")
        logger.info(f"가중치 - 키워드:{keyword_weight}, 시맨틱:{semantic_weight}, Re-rank:{rerank_weight}")
        
        results = []
        
        # Cross-Encoder 점수 계산 (사용하는 경우)
        rerank_scores = None
        if self.use_reranker and self.reranker is not None:
            try:
                pairs = [[search_query, doc] for doc in documents]
                rerank_scores = self.reranker.predict(pairs)
                logger.info("Cross-Encoder 점수 계산 완료")
            except Exception as e:
                logger.error(f"Cross-Encoder 실행 오류: {e}")
                rerank_scores = None
        
        # 각 문서에 대해 점수 계산
        for i in range(len(ids)):
            # 1. 키워드 매칭 점수
            keyword_score = self.calculate_keyword_score(query_keywords, documents[i])
            
            # 2. 시맨틱 유사도 점수 (거리 -> 유사도)
            semantic_score = max(0, 1 - distances[i])
            
            # 3. Re-ranker 점수 (정규화: -10~10 -> 0~1)
            if rerank_scores is not None:
                rerank_score = (rerank_scores[i] + 10) / 20  # 정규화
                rerank_score = max(0, min(1, rerank_score))  # 클리핑
            else:
                rerank_score = semantic_score  # Re-ranker 없으면 시맨틱 점수 사용
            
            # 4. 최종 점수 (가중 평균)
            final_score = (
                keyword_score * keyword_weight +
                semantic_score * semantic_weight +
                rerank_score * rerank_weight
            )
            
            score_details = {
                'keyword': round(keyword_score, 4),
                'semantic': round(semantic_score, 4),
                'rerank': round(rerank_score, 4),
                'final': round(final_score, 4)
            }
            
            results.append((
                ids[i],
                metadatas[i],
                documents[i],
                final_score,
                score_details
            ))
        
        # 최종 점수 기준으로 정렬
        results.sort(key=lambda x: x[3], reverse=True)
        
        logger.info("하이브리드 Re-ranking 완료")
        logger.info(f"상위 3개 점수: {[r[4] for r in results[:3]]}")
        
        return results
    
    async def suggest_stores(
        self,
        personnel: Optional[int] = None,
        region: Optional[str] = None,
        category_type: Optional[str] = None,
        user_keyword: str = "",
        n_results: int = 10,
        use_ai_enhancement: bool = False,
        min_similarity_threshold: float = 0.2,
        rerank_candidates_multiplier: int = 5,
        keyword_weight: float = 0.5,  # 키워드 매칭 가중치
        semantic_weight: float = 0.3,  # 시맨틱 유사도 가중치
        rerank_weight: float = 0.2     # Re-ranker 가중치
    ) -> List[Dict]:
        """
        개선된 매장 제안 (키워드 중심 하이브리드 검색)
        """
        logger.info("=" * 60)
        logger.info("개선된 매장 제안 요청")
        logger.info(f"  - 인원: {personnel}명")
        logger.info(f"  - 지역: {region}")
        logger.info(f"  - 타입: {category_type}")
        logger.info(f"  - 원본 키워드: {user_keyword}")
        logger.info(f"  - 가중치: 키워드={keyword_weight}, 시맨틱={semantic_weight}, Re-rank={rerank_weight}")
        logger.info("=" * 60)
        
        # 키워드 추출
        query_keywords = self.extract_keywords(user_keyword)
        logger.info(f"추출된 키워드: {query_keywords}")
        
        # 검색 쿼리 생성
        if use_ai_enhancement:
            search_query = await self.query_enhancer.enhance_query(
                personnel=personnel,
                category_type=category_type,
                user_keyword=user_keyword
            )
        else:
            query_parts = []
            if category_type:
                query_parts.append(category_type)
            query_parts.extend(query_keywords)
            search_query = " ".join(query_parts) if query_parts else user_keyword
        
        logger.info(f"최종 검색 쿼리: {search_query}")
        
        # 메타데이터 필터
        where_filter = None
        filter_conditions = []
        
        if region:
            filter_conditions.append({"region": region})
        
        if category_type:
            type_code = self.convert_type_to_code(category_type)
            if type_code:
                filter_conditions.append({"type_code": type_code})
        
        if len(filter_conditions) > 1:
            where_filter = {"$and": filter_conditions}
        elif len(filter_conditions) == 1:
            where_filter = filter_conditions[0]
        
        # 쿼리 임베딩
        query_embedding = self.embedding_model.encode(
            search_query,
            convert_to_tensor=True,
            show_progress_bar=False
        )
        
        if self.device == "cuda":
            query_embedding = query_embedding.cpu()
        
        # ChromaDB 검색
        search_n_results = n_results * rerank_candidates_multiplier
        
        try:
            results = self.store_collection.query(
                query_embeddings=[query_embedding.numpy().tolist()],
                n_results=search_n_results,
                where=where_filter,
                include=["metadatas", "documents", "distances"]
            )
            
            logger.info(f"ChromaDB 검색 결과: {len(results['ids'][0])}개")
            
        except Exception as e:
            logger.error(f"ChromaDB 검색 중 오류: {e}")
            return []
        
        if not results['ids'][0]:
            logger.warning("검색 결과가 없습니다.")
            return []
        
        # 하이브리드 Re-ranking
        reranked_results = self.hybrid_rerank(
            search_query=search_query,
            query_keywords=query_keywords,
            ids=results['ids'][0],
            metadatas=results['metadatas'][0],
            documents=results['documents'][0],
            distances=results['distances'][0],
            keyword_weight=keyword_weight,
            semantic_weight=semantic_weight,
            rerank_weight=rerank_weight
        )
        
        # 결과 포맷팅
        suggestions = []
        
        for store_id, metadata, document, final_score, score_details in reranked_results:
            try:
                if final_score < min_similarity_threshold:
                    continue
                
                suggestion = {
                    'store_id': metadata.get('store_id'),
                    'region': metadata.get('region'),
                    'type': metadata.get('type'),
                    'business_hour': metadata.get('business_hour'),
                    'similarity_score': final_score,
                    'score_breakdown': score_details,
                    'document': document,
                    'search_query': search_query
                }
                
                suggestions.append(suggestion)
                
                if len(suggestions) >= n_results:
                    break
                
            except Exception as e:
                logger.error(f"결과 처리 중 오류: {e}")
                continue
        
        logger.info(f"최종 제안 결과: {len(suggestions)}개")
        
        # 상위 3개 결과 로깅
        for i, sug in enumerate(suggestions[:3], 1):
            logger.info(f"순위 {i}: 최종점수={sug['similarity_score']:.4f}, 세부={sug['score_breakdown']}")
        
        return suggestions
    
    async def get_store_details(self, store_ids: List[str]) -> List[Dict]:
        """매장 상세 정보 조회"""
        from src.infra.database.repository.category_repository import CategoryRepository
        
        category_repo = CategoryRepository()
        store_details = []
        
        for store_id in store_ids:
            try:
                stores = await category_repo.select(id=store_id)
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