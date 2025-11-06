"""
개선된 매장 제안 서비스 (키워드 매칭 + 시맨틱 검색 하이브리드)
- 로컬 PersistentClient 또는 원격 Chroma HTTP 서버(AsyncHttpClient)를 모두 지원합니다.
- 비동기 초기화(init_async)를 사용해 chroma 클라이언트/컬렉션을 연결합니다.
"""
from typing import List, Dict, Optional, Tuple
import asyncio
import math
import re
import traceback

import torch
from sentence_transformers import SentenceTransformer, CrossEncoder

# chromadb는 로컬 PersistentClient 사용 시 필요
import chromadb
from chromadb.config import Settings

# 프로젝트 로그/외부 서비스 경로(프로젝트 구조에 맞게 경로를 조정하세요)
from src.infra.external.query_enchantment import QueryEnhancementService
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)

# 원격 Async HTTP 클라이언트를 따로 구현해두었다면 import하세요.
# infra/chroma_async_client.AsyncHttpClient 의존성을 사용합니다(있지 않다면 해당 모듈을 생성해야 합니다).
try:
    from infra.vector_database.chroma_connector import AsyncHttpClient  # type: ignore
except Exception:
    AsyncHttpClient = None  # 없을 수 있으므로 안전 처리


class StoreSuggestService:
    """
    StoreSuggestService

    Usage:
      svc = StoreSuggestService(use_remote_chroma=True, chroma_host="192.168.0.10", chroma_port=8000)
      await svc.init_async()
      suggestions = await svc.suggest_stores(user_keyword="분위기 좋은 카페", n_results=5)

    파라미터:
      persist_directory: 로컬 PersistentClient 사용 시 DB 경로 (로컬 사용 시 지정)
      use_remote_chroma: 원격 Chroma HTTP 서버 사용 여부
      chroma_host, chroma_port, chroma_ssl: 원격 서버 정보
      use_reranker: Cross-Encoder re-ranker 사용 여부
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        use_remote_chroma: bool = False,
        chroma_host: str = "localhost",
        chroma_port: int = 8081,
        chroma_ssl: bool = False,
        use_reranker: bool = True,
    ):
        logger.info("개선된 매장 제안 서비스 초기화 중...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"사용 중인 디바이스: {self.device}")

        self.persist_directory = persist_directory
        self.use_remote_chroma = use_remote_chroma
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.chroma_ssl = chroma_ssl

        # 모델 로드 (무거우므로 싱크 로드)
        logger.info("임베딩 모델 로딩 중: intfloat/multilingual-e5-large")
        self.embedding_model = SentenceTransformer("intfloat/multilingual-e5-large", device=self.device)
        logger.info("임베딩 모델 로딩 완료")

        self.use_reranker = use_reranker
        self.reranker = None
        if self.use_reranker:
            try:
                logger.info("Re-ranking 모델 로딩 중: BAAI/bge-reranker-base")
                self.reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=512, device=self.device)
                logger.info("Re-ranking 모델 로딩 완료")
            except Exception as e:
                logger.error(f"Re-ranking 모델 로딩 실패: {e}")
                self.use_reranker = False
                self.reranker = None

        self.query_enhancer = QueryEnhancementService()

        # chroma client/collection 초기값 (async init에서 설정)
        self.client = None
        self.store_collection = None

    async def init_async(self):
        """
        비동기 초기화: 로컬 PersistentClient 또는 원격 AsyncHttpClient에 연결합니다.
        반드시 async context에서 호출하세요.
        """
        if self.use_remote_chroma:
            if AsyncHttpClient is None:
                raise RuntimeError("원격 AsyncHttpClient 모듈(infra.chroma_async_client)이 없습니다.")
            logger.info(f"원격 Chroma 서버에 연결: {self.chroma_host}:{self.chroma_port}")
            # AsyncHttpClient는 비동기 팩토리로 가정
            self.client = await AsyncHttpClient(host=self.chroma_host, port=self.chroma_port, ssl=self.chroma_ssl)
            # get_collection은 비동기 메서드를 제공하는 AsyncCollection을 반환한다고 가정
            self.store_collection = await self.client.get_collection("stores")
            try:
                # count도 비동기일 수 있으니 검사
                if asyncio.iscoroutinefunction(getattr(self.store_collection, "count", lambda: None)):
                    count = await self.store_collection.count()
                else:
                    count = await asyncio.to_thread(self.store_collection.count)
                logger.info(f"매장 컬렉션 로드 완료: {count}개 매장")
            except Exception:
                logger.info("매장 컬렉션 로드 완료 (개수 조회 실패)")
        else:
            # 로컬 PersistentClient 사용 (동기)
            logger.info(f"로컬 PersistentClient 열기: path={self.persist_directory}")
            try:
                self.client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(anonymized_telemetry=False, allow_reset=True),
                )
                self.store_collection = self.client.get_collection(name="stores")
                # count는 sync이므로 to_thread로 호출하지 않아도 되지만 init_async는 async이므로 to_thread로 감쌈
                count = await asyncio.to_thread(self.store_collection.count)
                logger.info(f"로컬 매장 컬렉션 로드 완료: {count}개 매장")
            except Exception as e:
                logger.error(f"로컬 Chroma 컬렉션 로드 실패: {e}")
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
        동기 함수로 구현되어 있으며, async 컨텍스트에서 호출 시 asyncio.to_thread로 실행하세요.
        """
        logger.info(f"하이브리드 Re-ranking 시작: {len(ids)}개 문서")
        results = []

        # Cross-Encoder 점수 계산 (동기)
        rerank_scores = None
        if self.use_reranker and self.reranker is not None:
            try:
                pairs = [[search_query, doc] for doc in documents]
                rerank_scores = self.reranker.predict(pairs)
                logger.info("Cross-Encoder 점수 계산 완료")
            except Exception as e:
                logger.error(f"Cross-Encoder 실행 오류: {e}")
                rerank_scores = None

        for i in range(len(ids)):
            keyword_score = self.calculate_keyword_score(query_keywords, documents[i])
            semantic_score = max(0.0, 1.0 - distances[i]) if distances is not None and len(distances) > i else 0.0

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
        logger.info("하이브리드 Re-ranking 완료")
        if results:
            logger.info(f"상위 3개 점수: {[r[4] for r in results[:3]]}")
        return results

    async def _collection_query(self, query_embeddings, n_results, where_filter, include):
        """
        컬렉션의 query를 안전하게 호출 (동기 컬렉션이면 to_thread로, 비동기면 await로).
        query_embeddings는 리스트 형태(예: [embedding_list]).
        """
        if self.store_collection is None:
            raise RuntimeError("Chroma 컬렉션이 초기화되지 않았습니다. init_async를 호출하세요.")

        query_fn = getattr(self.store_collection, "query", None)
        if query_fn is None:
            raise RuntimeError("store_collection에 query 메서드가 없습니다.")

        # 바운드 메서드가 코루틴 함수인지 확인
        if asyncio.iscoroutinefunction(query_fn):
            # async method
            return await query_fn(query_embeddings=query_embeddings, n_results=n_results, where=where_filter, include=include)
        else:
            # sync method: 블로킹이므로 to_thread로 실행
            return await asyncio.to_thread(query_fn, query_embeddings=query_embeddings, n_results=n_results, where=where_filter, include=include)

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
        """
        logger.info("=" * 60)
        logger.info("개선된 매장 제안 요청")
        logger.info(f"  - 인원: {personnel}명")
        logger.info(f"  - 지역: {region}")
        logger.info(f"  - 타입: {category_type}")
        logger.info(f"  - 원본 키워드: {user_keyword}")
        logger.info("=" * 60)

        query_keywords = self.extract_keywords(user_keyword)
        logger.info(f"추출된 키워드: {query_keywords}")

        query_keywords = self.preprocess_keywords(query_keywords)
        logger.info(f"전처리된 키워드: {query_keywords}")

        if use_ai_enhancement:
            try:
                search_query = await self.query_enhancer.enhance_query(personnel=personnel, category_type=category_type, user_keyword=user_keyword)
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

        # 메타데이터 필터 작성
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

        # 쿼리 임베딩 생성 (torch tensor)
        query_embedding = self.embedding_model.encode(search_query, convert_to_tensor=True, show_progress_bar=False)
        if self.device == "cuda":
            query_embedding = query_embedding.cpu()

        # numpy/list로 변환
        if hasattr(query_embedding, "numpy"):
            emb_list = query_embedding.numpy().tolist()
        else:
            # 이미 list인 경우
            emb_list = query_embedding

        search_n_results = n_results * rerank_candidates_multiplier

        try:
            results = await self._collection_query(query_embeddings=[emb_list], n_results=search_n_results, where_filter=where_filter, include=["metadatas", "documents", "distances"])
            # results expected format: dict with keys: ids, metadatas, documents, distances (each is list of lists)
            ids = results.get("ids", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            logger.info(f"ChromaDB 검색 결과: {len(ids)}개")
        except Exception as e:
            logger.error(f"ChromaDB 검색 중 오류: {e}")
            logger.error(traceback.format_exc())
            return []

        if not ids:
            logger.warning("검색 결과가 없습니다.")
            return []

        # hybrid_rerank는 동기 함수이므로 to_thread로 실행해서 메인 이벤트 루프 차단 방지
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
            logger.error(f"Re-ranking 중 오류: {e}")
            logger.error(traceback.format_exc())
            return []

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
                logger.error(traceback.format_exc())
                continue

        logger.info(f"최종 제안 결과: {len(suggestions)}개")
        for i, sug in enumerate(suggestions[:3], 1):
            logger.info(f"순위 {i}: 최종점수={sug['similarity_score']:.4f}, 세부={sug['score_breakdown']}")

        return suggestions

    async def get_store_details(self, store_ids: List[str]) -> List[Dict]:
        """
        매장 상세 정보 조회 (비동기)
        - 내부 CategoryRepository의 select 메서드가 비동기(예상)라고 가정하고 await 사용.
        """
        from src.infra.database.repository.category_repository import CategoryRepository  # 로컬 import

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
                logger.error(traceback.format_exc())
                continue

        return store_details