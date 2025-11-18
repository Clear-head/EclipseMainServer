"""
개선된 매장 제안 서비스 (키워드 매칭 + 시맨틱 검색 하이브리드)
"""
import asyncio
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

import torch
from sentence_transformers import SentenceTransformer, CrossEncoder

from src.infra.external.query_enchantment import QueryEnhancementService
from src.infra.vector_database.chroma_connector import AsyncHttpClient
from src.logger.custom_logger import get_logger
from src.utils.path import path_dic

logger = get_logger(__name__)


class StoreSuggestService:
    """개선된 매장 제안 서비스 (키워드 매칭 중심)"""
    
    def __init__(self, use_reranker: bool = True):
        """
        Args:
            use_reranker: Re-ranking 모델 사용 여부
        """
        logger.info("개선된 매장 제안 서비스 초기화 중...")
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"사용 중인 디바이스: {self.device}")
        
        # 설정 파일 로드
        self.config = self._load_config()
        self.chroma_config = self.config.get("chroma", {})
        
        # ChromaDB 클라이언트 초기화 (비동기)
        self.client = None
        self.store_collection = None
        
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
    
    def _load_config(self) -> Dict:
        """database_config.json 파일 로드"""
        config_path = path_dic.get("database_config")
        
        if not config_path or not Path(config_path).exists():
            logger.error(f"설정 파일을 찾을 수 없습니다: {config_path}")
            raise FileNotFoundError(f"설정 파일 없음: {config_path}")
        
        logger.info(f"설정 파일 로드: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        logger.info(f"설정 파일 로드 완료 (버전: {config.get('version')})")
        return config
    
    async def _initialize_client(self):
        """ChromaDB 클라이언트 초기화 (비동기)"""
        if self.client is not None:
            return  # 이미 초기화됨
        
        mode = self.chroma_config.get("mode", "local")
        
        if mode == "remote":
            # 원격 서버 연결
            host = self.chroma_config.get("host", "localhost")
            port = self.chroma_config.get("port", 8081)
            ssl = self.chroma_config.get("ssl", False)
            
            logger.info(f"원격 ChromaDB 서버 연결 중: {host}:{port} (SSL: {ssl})")
            
            try:
                self.client = await AsyncHttpClient(
                    host=host,
                    port=port,
                    ssl=ssl
                )
                
                # 연결 확인
                await self.client.heartbeat()
                logger.info("원격 ChromaDB 서버 연결 성공")
                
            except Exception as e:
                logger.error(f"원격 ChromaDB 서버 연결 실패: {e}")
                raise
        
        else:
            # 로컬 모드 (PersistentClient)
            import chromadb
            from chromadb.config import Settings
            
            persist_directory = self.chroma_config.get("path", "./chroma_db")
            logger.info(f"로컬 ChromaDB 초기화 중: {persist_directory}")
            
            # 동기 클라이언트를 비동기 래퍼로 감싸기
            sync_client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # 간단한 비동기 래퍼
            class _AsyncLocalClient:
                def __init__(self, sync_client):
                    self._sync = sync_client
                
                async def get_collection(self, name: str):
                    from src.infra.vector_database.chroma_connector import AsyncHttpClient
                    # AsyncHttpClient의 _AsyncCollection과 호환되는 래퍼
                    sync_col = await asyncio.to_thread(self._sync.get_collection, name)
                    
                    class _AsyncCollection:
                        def __init__(self, sync_collection):
                            self._sync = sync_collection
                        
                        async def query(self, *args, **kwargs):
                            return await asyncio.to_thread(self._sync.query, *args, **kwargs)
                        
                        async def count(self):
                            return await asyncio.to_thread(self._sync.count)
                        
                        @property
                        def name(self):
                            return self._sync.name
                    
                    return _AsyncCollection(sync_col)
            
            self.client = _AsyncLocalClient(sync_client)
            logger.info("로컬 ChromaDB 초기화 완료")
        
        # 컬렉션 로드
        try:
            self.store_collection = await self.client.get_collection(name="stores")
            count = await self.store_collection.count()
            logger.info(f"매장 컬렉션 로드 완료: {count}개 매장")
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
        keywords = re.split(r'[,\s]+', text)
        keywords = [k.strip() for k in keywords if k.strip()]
        return keywords
    
    async def calculate_keyword_score(self, query_keywords: List[str], document: str) -> float:
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
        
        matches = 0
        total_occurrences = 0
        
        for keyword in query_keywords:
            keyword_lower = keyword.lower()
            count = doc_lower.count(keyword_lower)
            if count > 0:
                matches += 1
                total_occurrences += count
        
        match_ratio = matches / len(query_keywords)
        
        import math
        frequency_score = math.log1p(total_occurrences) / 5.0
        
        final_score = (match_ratio * 0.7) + (min(frequency_score, 1.0) * 0.3)
        
        return final_score
    
    async def hybrid_rerank(
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
            keyword_weight: 키워드 매칭 가중치
            semantic_weight: 시맨틱 유사도 가중치
            rerank_weight: Re-ranker 가중치
            
        Returns:
            List[tuple]: (id, metadata, document, final_score, score_details)
        """
        logger.info(f"하이브리드 Re-ranking 시작: {len(ids)}개 문서")
        logger.info(f"가중치 - 키워드:{keyword_weight}, 시맨틱:{semantic_weight}, Re-rank:{rerank_weight}")
        
        results = []
        
        # Cross-Encoder 점수 계산
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
            keyword_score = self.calculate_keyword_score(query_keywords, documents[i])
            semantic_score = max(0, 1 - distances[i])
            
            if rerank_scores is not None:
                rerank_score = (rerank_scores[i] + 10) / 20
                rerank_score = max(0, min(1, rerank_score))
            else:
                rerank_score = semantic_score
            
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
        
        results.sort(key=lambda x: x[3], reverse=True)
        
        logger.info("하이브리드 Re-ranking 완료")
        logger.info(f"상위 3개 점수: {[r[4] for r in results[:3]]}")
        
        return results
    
    def preprocess_keywords(self, keywords: List[str]) -> List[str]:
        """
        키워드 전처리 (동의어 치환)
        
        Args:
            keywords: 원본 키워드 리스트
            
        Returns:
            List[str]: 치환된 키워드 리스트
        """
        synonym_map = {
            "중국집": "중식당",
            "중국요리": "중식당",
            "중국음식": "중식당",
            "한식집": "한식",
        }
        
        processed_keywords = []
        for keyword in keywords:
            processed = synonym_map.get(keyword.strip(), keyword.strip())
            processed_keywords.append(processed)
            
            if processed != keyword.strip():
                logger.info(f"키워드 치환: '{keyword}' → '{processed}'")
        
        return processed_keywords
    
    async def suggest_stores(
        self,
        personnel: Optional[int] = None,
        region: Optional[str] = None,
        category_type: Optional[str] = None,
        user_keyword: str = "",
        n_results: int = 20,
        use_ai_enhancement: bool = False,
        min_similarity_threshold: float = 0.2,
        rerank_candidates_multiplier: int = 5,
        keyword_weight: float = 0.75,
        semantic_weight: float = 0.2,
        rerank_weight: float = 0.1
    ) -> List[Dict]:
        """개선된 매장 제안 (키워드 중심 하이브리드 검색)"""
        
        # 클라이언트 초기화 (최초 1회만)
        await self._initialize_client()
        
        logger.info("=" * 60)
        logger.info("개선된 매장 제안 요청")
        logger.info(f"  - 인원: {personnel}명")
        logger.info(f"  - 지역: {region}")
        logger.info(f"  - 타입: {category_type}")
        logger.info(f"  - 원본 키워드: {user_keyword}")
        logger.info("=" * 60)
        
        # 키워드 추출 및 전처리
        query_keywords = self.extract_keywords(user_keyword)
        logger.info(f"추출된 키워드: {query_keywords}")
        
        query_keywords = self.preprocess_keywords(query_keywords)
        logger.info(f"전처리된 키워드: {query_keywords}")
        
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
        
        # ChromaDB 검색 (비동기)
        search_n_results = n_results * rerank_candidates_multiplier
        
        try:
            results = await self.store_collection.query(
                query_embeddings=[query_embedding.numpy().tolist()],
                n_results=search_n_results,
                where=where_filter,
                include=["metadatas", "documents", "distances"]
            )
            
            logger.info(f"ChromaDB 검색 결과: {len(results['ids'][0])}개")
            
        except Exception as e:
            logger.error(f"ChromaDB 검색 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
        """매장 상세 정보 조회 (리뷰 통계 포함)"""
        from src.infra.database.repository.category_repository import CategoryRepository
        
        category_repo = CategoryRepository()
        
        try:
            # 새로운 메서드 사용 (LEFT JOIN으로 리뷰 없는 매장도 포함)
            store_details_dto = await category_repo.get_review_statistics(
                id=store_ids,
                only_reviewed=False,
                is_random=True
            )
            
            # DTO를 Dict로 변환
            store_details = []
            for dto in store_details_dto:
                store_details.append({
                    'id': dto.id,
                    'name': dto.title,
                    'image': dto.image_url,
                    'detail_address': dto.detail_address,
                    'sub_category': dto.sub_category,
                    'latitude': float(dto.lat) if dto.lat else None,
                    'longitude': float(dto.lng) if dto.lng else None,
                    'review_count': dto.review_count,
                    'average_stars': dto.average_stars,
                    # DTO에 없는 필드는 기본값
                    'do': '',
                    'si': '',
                    'gu': '',
                    'business_hour': '',
                    'phone': '',
                    'type': '',
                    'menu': '정보없음'
                })
            
            return store_details
            
        except Exception as e:
            logger.error(f"매장 상세 정보 조회 중 오류: {e}")
            return []


    async def get_random_stores_from_db(
        self,
        region: str,
        category_type: str,
        n_results: int = 10
    ) -> List[Dict]:
        """
        DB에서 지역과 카테고리 기반 매장 조회
        1순위: 리뷰가 있는 매장 중 평점 높은 순 (1개라도 있으면 반환)
        2순위: 리뷰 없어도 조건 맞는 랜덤 매장
        
        Args:
            region: 지역명 (예: "강남구")
            category_type: 카테고리 타입 (예: "카페")
            n_results: 결과 개수
        
        Returns:
            매장 리스트 (리뷰 통계 포함)
        """
        from src.infra.database.repository.category_repository import CategoryRepository
        
        logger.info(f"DB 조회 시작: {category_type} in {region}")
        
        repo = CategoryRepository()
        type_code = self.convert_type_to_code(category_type)
        
        # 1차 시도: 리뷰가 있는 매장 중 평점 높은 순
        stores_with_reviews = await repo.get_review_statistics(
            limit=n_results,
            gu=region,
            type=type_code,
            only_reviewed=True,
            is_random=False,  # INNER JOIN (리뷰 있는 매장만)
            order_by_rating=True  # 평점 높은 순 정렬
        )
        
        # 1개라도 있으면 바로 반환
        if stores_with_reviews:
            logger.info(f"리뷰 있는 매장 조회 성공: {len(stores_with_reviews)}개 (평점순)")
            return [store.model_dump() for store in stores_with_reviews]
        
        # 2차 시도: 리뷰 조건 없이 랜덤 조회
        logger.warning("리뷰 있는 매장 없음. 전체 매장에서 랜덤 조회 시도")
        
        all_stores = await repo.get_review_statistics(
            limit=n_results,
            gu=region,
            type=type_code,
            only_reviewed=False,  # LEFT JOIN (모든 매장)
            is_random=True,  # 랜덤
            order_by_rating=False  
        )
        
        if not all_stores:
            logger.error(f"해당 조건의 매장이 전혀 없습니다: {category_type} in {region}")
            return []
        
        logger.info(f"전체 매장 랜덤 조회 결과: {len(all_stores)}개")
        return [store.model_dump() for store in all_stores]