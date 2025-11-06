"""
개선된 매장 제안 서비스 (키워드 매칭 + 시맨틱 검색 하이브리드)
- database_config.json에서 chroma 설정 자동 로드
- 로컬/원격 Chroma DB 모두 지원
"""
from typing import List, Dict, Optional, Tuple
import asyncio
import math
import re
import traceback
import json

import torch
from sentence_transformers import SentenceTransformer, CrossEncoder
import chromadb
from chromadb.config import Settings

from infra.vector_database.chroma_connector import AsyncHttpClient
from src.infra.external.query_enchantment import QueryEnhancementService
from src.logger.custom_logger import get_logger
from src.utils.path import path_dic

logger = get_logger(__name__)


class StoreSuggestService:
    """
    매장 제안 서비스
    
    database_config.json의 chroma 설정을 자동으로 로드하여 사용합니다.
    - mode: "local" - 로컬 PersistentClient 사용
    - mode: "remote" - 원격 HTTP 서버 사용
    
    Usage:
        svc = StoreSuggestService()
        await svc.init_async()
        results = await svc.suggest_stores(user_keyword="분위기 좋은 카페")
    """

    def __init__(self, use_reranker: bool = True):
        """
        Args:
            use_reranker: Cross-Encoder re-ranker 사용 여부
        """
        logger.info("=" * 60)
        logger.info("매장 제안 서비스 초기화 중...")
        logger.info("=" * 60)
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"✓ 사용 디바이스: {self.device}")

        # database_config.json에서 chroma 설정 로드
        self.chroma_config = self._load_chroma_config()
        logger.info(
            f"✓ Chroma 설정: mode={self.chroma_config['mode']}, "
            f"host={self.chroma_config.get('host', 'N/A')}, "
            f"port={self.chroma_config.get('port', 'N/A')}"
        )

        # 임베딩 모델 로드
        logger.info("임베딩 모델 로딩 중: intfloat/multilingual-e5-large")
        self.embedding_model = SentenceTransformer(
            "intfloat/multilingual-e5-large",
            device=self.device
        )
        logger.info("✓ 임베딩 모델 로딩 완료")

        # Re-ranker 모델 로드
        self.use_reranker = use_reranker
        self.reranker = None
        if self.use_reranker:
            try:
                logger.info("Re-ranking 모델 로딩 중: BAAI/bge-reranker-base")
                self.reranker = CrossEncoder(
                    "BAAI/bge-reranker-base",
                    max_length=512,
                    device=self.device
                )
                logger.info("✓ Re-ranking 모델 로딩 완료")
            except Exception as e:
                logger.error(f"✗ Re-ranking 모델 로딩 실패: {e}")
                self.use_reranker = False

        self.query_enhancer = QueryEnhancementService()

        # Chroma 클라이언트/컬렉션 (init_async에서 초기화)
        self.client = None
        self.store_collection = None
        
        logger.info("=" * 60)

    def _load_chroma_config(self) -> Dict:
        """database_config.json에서 chroma 설정 로드"""
        config_path = path_dic["database_config"]
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            chroma_config = config.get("chroma", {})
            
            # 기본값 설정
            chroma_config.setdefault("mode", "local")
            chroma_config.setdefault("host", "localhost")
            chroma_config.setdefault("port", 8081)
            chroma_config.setdefault("ssl", False)
            chroma_config.setdefault("path", "./chroma_db")
            
            return chroma_config
            
        except Exception as e:
            logger.error(f"database_config.json 로드 실패: {e}")
            # 기본값 반환
            return {
                "mode": "local",
                "host": "localhost",
                "port": 8081,
                "ssl": False,
                "path": "./chroma_db"
            }

    async def init_async(self):
        """
        비동기 초기화: Chroma DB 연결
        database_config.json의 설정에 따라 로컬/원격 자동 선택
        """
        mode = self.chroma_config.get("mode", "local")
        
        if mode == "remote":
            # 원격 HTTP 서버 연결
            host = self.chroma_config["host"]
            port = self.chroma_config["port"]
            ssl = self.chroma_config.get("ssl", False)
            
            logger.info(f"원격 Chroma 서버 연결 중: {host}:{port}")
            
            try:
                self.client = await AsyncHttpClient(
                    host=host,
                    port=port,
                    ssl=ssl
                )
                
                # 연결 테스트
                heartbeat = await self.client.heartbeat()
                logger.info(f"✓ 서버 연결 성공: {heartbeat}")
                
                # 컬렉션 로드
                self.store_collection = await self.client.get_collection("stores")
                count = await self.store_collection.count()
                logger.info(f"✓ 매장 컬렉션 로드 완료: {count}개 매장")
                
            except Exception as e:
                logger.error(f"✗ 원격 Chroma 서버 연결 실패: {e}")
                logger.error(traceback.format_exc())
                raise RuntimeError(
                    f"Chroma 서버({host}:{port})에 연결할 수 없습니다.\n"
                    f"서버 실행 확인: chroma run --path ./chroma_db --host 0.0.0.0 --port {port}\n"
                    f"방화벽 확인: 포트 {port}가 열려있는지 확인하세요."
                )
                
        else:
            # 로컬 PersistentClient 사용
            path = self.chroma_config.get("path", "./chroma_db")
            logger.info(f"로컬 Chroma DB 열기: {path}")
            
            try:
                self.client = chromadb.PersistentClient(
                    path=path,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                self.store_collection = self.client.get_collection(name="stores")
                count = await asyncio.to_thread(self.store_collection.count)
                logger.info(f"✓ 로컬 매장 컬렉션 로드 완료: {count}개 매장")
                
            except Exception as e:
                logger.error(f"✗ 로컬 Chroma DB 로드 실패: {e}")
                logger.error(traceback.format_exc())
                raise

    @staticmethod
    def convert_type_to_code(type_korean: str) -> str:
        """한글 타입을 코드로 변환"""
        type_map = {"음식점": "0", "카페": "1", "콘텐츠": "2"}
        return type_map.get(type_korean, "")

    def extract_keywords(self, text: str) -> List[str]:
        """텍스트에서 키워드 추출 (쉼표, 공백 기준)"""
        keywords = re.split(r"[,\s]+", text)
        keywords = [k.strip() for k in keywords if k.strip()]
        return keywords

    def calculate_keyword_score(self, query_keywords: List[str], document: str) -> float:
        """
        키워드 매칭 점수 계산 (간단 BM25 스타일)
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
        frequency_score = math.log1p(total_occurrences) / 5.0
        final_score = (match_ratio * 0.7) + (min(frequency_score, 1.0) * 0.3)
        return final_score

    def preprocess_keywords(self, keywords: List[str]) -> List[str]:
        """
        키워드 전처리 (동의어 치환)
        """
        synonym_map = {
            "중국집": "중식당",
            "중국요리": "중식당",
            "중국음식": "중식당",
            "한식집": "한식",
            # 필요에 따라 추가
        }

        processed_keywords = []
        for keyword in keywords:
            processed = synonym_map.get(keyword.strip(), keyword.strip())
            processed_keywords.append(processed)
            if processed != keyword.strip():
                logger.info(f"키워드 치환: '{keyword}' → '{processed}'")
        return processed_keywords

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
        rerank_weight: float = 0.2,
    ) -> List[Tuple[str, Dict, str, float, Dict]]:
        """
        하이브리드 Re-ranking: 키워드 + 시맨틱 + Cross-Encoder
        """
        logger.info(f"하이브리드 Re-ranking 시작: {len(ids)}개 문서")
        results = []

        # Cross-Encoder 점수 계산
        rerank_scores = None
        if self.use_reranker and self.reranker is not None:
            try:
                pairs = [[search_query, doc] for doc in documents]
                rerank_scores = self.reranker.predict(pairs)
                logger.info("✓ Cross-Encoder 점수 계산 완료")
            except Exception as e:
                logger.error(f"✗ Cross-Encoder 실행 오류: {e}")

        for i in range(len(ids)):
            keyword_score = self.calculate_keyword_score(query_keywords, documents[i])
            semantic_score = max(0.0, 1.0 - distances[i])

            if rerank_scores is not None:
                rerank_score = (rerank_scores[i] + 10) / 20.0
                rerank_score = max(0.0, min(1.0, rerank_score))
            else:
                rerank_score = semantic_score

            final_score = (
                keyword_score * keyword_weight
                + semantic_score * semantic_weight
                + rerank_score * rerank_weight
            )

            score_details = {
                "keyword": round(keyword_score, 4),
                "semantic": round(semantic_score, 4),
                "rerank": round(rerank_score, 4),
                "final": round(final_score, 4),
            }

            results.append((ids[i], metadatas[i], documents[i], final_score, score_details))

        results.sort(key=lambda x: x[3], reverse=True)
        logger.info("✓ 하이브리드 Re-ranking 완료")
        if results:
            logger.info(f"상위 3개 점수: {[r[4] for r in results[:3]]}")
        return results

    async def _collection_query(self, query_embeddings, n_results, where_filter, include):
        """컬렉션 쿼리 실행 (동기/비동기 자동 처리)"""
        if self.store_collection is None:
            raise RuntimeError("Chroma 컬렉션이 초기화되지 않았습니다. init_async()를 호출하세요.")

        query_fn = getattr(self.store_collection, "query", None)
        if query_fn is None:
            raise RuntimeError("store_collection에 query 메서드가 없습니다.")

        if asyncio.iscoroutinefunction(query_fn):
            # 비동기 메서드
            return await query_fn(
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where_filter,
                include=include
            )
        else:
            # 동기 메서드 - to_thread로 실행
            return await asyncio.to_thread(
                query_fn,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where_filter,
                include=include
            )

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
        rerank_weight: float = 0.05,
    ) -> List[Dict]:
        """
        개선된 매장 제안 (비동기)
        
        Args:
            personnel: 인원 수
            region: 지역 (예: "강남구")
            category_type: 카테고리 타입 (예: "카페", "음식점", "콘텐츠")
            user_keyword: 사용자 검색 키워드
            n_results: 반환할 결과 개수
            use_ai_enhancement: AI 쿼리 개선 사용 여부
            min_similarity_threshold: 최소 유사도 임계값
            rerank_candidates_multiplier: Re-ranking 후보 배수
            keyword_weight: 키워드 매칭 가중치
            semantic_weight: 시맨틱 유사도 가중치
            rerank_weight: Re-ranker 가중치
            
        Returns:
            List[Dict]: 매장 제안 결과 리스트
        """
        logger.info("=" * 60)
        logger.info("매장 제안 요청")
        logger.info(f"  - 인원: {personnel}명")
        logger.info(f"  - 지역: {region}")
        logger.info(f"  - 타입: {category_type}")
        logger.info(f"  - 키워드: {user_keyword}")
        logger.info("=" * 60)

        # 키워드 추출 및 전처리
        query_keywords = self.extract_keywords(user_keyword)
        query_keywords = self.preprocess_keywords(query_keywords)
        logger.info(f"전처리된 키워드: {query_keywords}")

        # 검색 쿼리 생성
        if use_ai_enhancement:
            try:
                search_query = await self.query_enhancer.enhance_query(
                    personnel=personnel,
                    category_type=category_type,
                    user_keyword=user_keyword
                )
            except Exception as e:
                logger.error(f"쿼리 개선 실패: {e}")
                search_query = " ".join([category_type or "", user_keyword]).strip()
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

        # 쿼리 임베딩 생성
        query_embedding = self.embedding_model.encode(
            search_query,
            convert_to_tensor=True,
            show_progress_bar=False
        )
        if self.device == "cuda":
            query_embedding = query_embedding.cpu()

        emb_list = query_embedding.numpy().tolist()
        search_n_results = n_results * rerank_candidates_multiplier

        # Chroma DB 검색
        try:
            results = await self._collection_query(
                query_embeddings=[emb_list],
                n_results=search_n_results,
                where_filter=where_filter,
                include=["metadatas", "documents", "distances"]
            )
            
            ids = results.get("ids", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            
            logger.info(f"✓ ChromaDB 검색 완료: {len(ids)}개")
            
        except Exception as e:
            logger.error(f"✗ ChromaDB 검색 중 오류: {e}")
            logger.error(traceback.format_exc())
            return []

        if not ids:
            logger.warning("검색 결과가 없습니다.")
            return []

        # 하이브리드 Re-ranking
        try:
            reranked_results = await asyncio.to_thread(
                self.hybrid_rerank,
                search_query,
                query_keywords,
                ids,
                metadatas,
                documents,
                distances,
                keyword_weight,
                semantic_weight,
                rerank_weight,
            )
        except Exception as e:
            logger.error(f"✗ Re-ranking 중 오류: {e}")
            logger.error(traceback.format_exc())
            return []

        # 결과 포맷팅
        suggestions: List[Dict] = []
        for store_id, metadata, document, final_score, score_details in reranked_results:
            try:
                if final_score < min_similarity_threshold:
                    continue

                suggestion = {
                    "store_id": metadata.get("store_id"),
                    "region": metadata.get("region"),
                    "type": metadata.get("type"),
                    "business_hour": metadata.get("business_hour"),
                    "similarity_score": final_score,
                    "score_breakdown": score_details,
                    "document": document,
                    "search_query": search_query,
                }
                suggestions.append(suggestion)
                
                if len(suggestions) >= n_results:
                    break
                    
            except Exception as e:
                logger.error(f"결과 처리 중 오류: {e}")
                continue

        logger.info(f"✓ 최종 제안 결과: {len(suggestions)}개")
        for i, sug in enumerate(suggestions[:3], 1):
            logger.info(
                f"  순위 {i}: 점수={sug['similarity_score']:.4f}, "
                f"세부={sug['score_breakdown']}"
            )
        logger.info("=" * 60)

        return suggestions

    async def get_store_details(self, store_ids: List[str]) -> List[Dict]:
        """
        매장 상세 정보 조회
        
        Args:
            store_ids: 매장 ID 리스트
            
        Returns:
            List[Dict]: 매장 상세 정보 리스트
        """
        from src.infra.database.repository.category_repository import CategoryRepository

        category_repo = CategoryRepository()
        store_details = []

        for store_id in store_ids:
            try:
                stores = await category_repo.select(id=store_id)
                if stores and len(stores) > 0:
                    store = stores[0]
                    store_dict = {
                        "id": store.id,
                        "name": store.name,
                        "do": store.do,
                        "si": store.si,
                        "gu": store.gu,
                        "detail_address": store.detail_address,
                        "sub_category": store.sub_category,
                        "business_hour": store.business_hour,
                        "phone": store.phone,
                        "type": store.type,
                        "image": store.image,
                        "latitude": store.latitude,
                        "longitude": store.longitude,
                        "menu": store.menu,
                    }
                    store_details.append(store_dict)
            except Exception as e:
                logger.error(f"매장 ID '{store_id}' 조회 중 오류: {e}")
                continue

        return store_details