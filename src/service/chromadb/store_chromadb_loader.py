"""
ChromaDB 데이터 적재 모듈
매장 정보를 키워드 중심 문서로 저장합니다.
"""
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict
from src.logger.custom_logger import get_logger
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.infra.database.repository.tags_repository import TagsRepository

logger = get_logger(__name__)


class StoreChromaDBLoader:
    """매장 데이터를 ChromaDB에 적재하는 클래스"""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Args:
            persist_directory: ChromaDB 저장 경로
        """
        logger.info("ChromaDB 초기화 중...")
        
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 임베딩 모델 설정
        logger.info("임베딩 모델 로딩 중: intfloat/multilingual-e5-large")
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="intfloat/multilingual-e5-large"
        )
        logger.info("임베딩 모델 로딩 완료")
        
        # 컬렉션 생성 (임베딩 함수 적용)
        self.store_collection = self.client.get_or_create_collection(
            name="stores",
            metadata={"description": "매장 정보 검색용 컬렉션 (임베딩)"},
            embedding_function=self.embedding_function
        )
        
        logger.info(f"ChromaDB 초기화 완료: {persist_directory}")
    
    @staticmethod
    def convert_type_to_korean(type_value: int) -> str:
        """
        타입 숫자를 한글로 변환
        
        Args:
            type_value: 타입 숫자 (0: 음식점, 1: 카페, 2: 콘텐츠)
            
        Returns:
            str: 한글 타입명
        """
        type_map = {
            0: "음식점",
            1: "카페",
            2: "콘텐츠"
        }
        return type_map.get(type_value, "기타")
    
    def create_store_document(self, store_entity, tags: List[Dict]) -> str:
        """
        매장 데이터를 자연스러운 한국어 문장으로 변환
        구, 타입, 영업시간은 문서에서 제외 (메타데이터로 필터링/조회)
        sub_category와 타입이 콘텐츠일 경우 매장명 포함
        
        Args:
            store_entity: CategoryEntity 객체
            tags: 태그 목록 [{'name': '태그명', 'count': 개수}, ...]
            
        Returns:
            str: 자연스러운 한국어 문장 (구, 타입, 매장ID, 영업시간 제외)
        """
        # 태그 처리: 1등 제외하고 2~11위까지 (상위 10개)
        sorted_tags = sorted(tags, key=lambda x: x['count'], reverse=True)
        if len(sorted_tags) > 1:
            selected_tags = sorted_tags[1:11]  # 2~11위
        else:
            selected_tags = []
        
        tags_list = [tag['name'] for tag in selected_tags]
        
        # 메뉴/키워드
        menu_or_keywords = store_entity.menu if store_entity.menu else ""
        
        # sub_category
        sub_category = store_entity.sub_category if store_entity.sub_category else ""
        
        # 자연스러운 한국어 문장 생성
        doc_parts = []
        
        # 콘텐츠 타입일 경우 매장명 추가
        if store_entity.type == 2:  # 콘텐츠
            store_name = store_entity.name if store_entity.name else ""
            if store_name:
                name_sentence = f"{store_name}은(는)"
                doc_parts.append(name_sentence)
        
        # sub_category 문장 추가
        if sub_category:
            sub_categories = [cat.strip() for cat in sub_category.split(',') if cat.strip()]
            if sub_categories:
                if len(sub_categories) > 1:
                    sub_cat_sentence = f"{', '.join(sub_categories[:-1])}, {sub_categories[-1]} 카테고리에 속합니다."
                else:
                    sub_cat_sentence = f"{sub_categories[0]} 카테고리에 속합니다."
                doc_parts.append(sub_cat_sentence)
        
        # 태그를 문장으로 변환
        if tags_list:
            tags_clean = [tag.replace('"', '').strip() for tag in tags_list]
            if len(tags_clean) > 1:
                tags_sentence = f"이 장소는 {', '.join(tags_clean[:-1])}, {tags_clean[-1]}의 특징을 가지고 있습니다."
            else:
                tags_sentence = f"이 장소는 {tags_clean[0]}의 특징을 가지고 있습니다."
            doc_parts.append(tags_sentence)
        
        # type에 따라 메뉴/키워드 문장 다르게 생성
        if menu_or_keywords:
            items = [item.strip() for item in menu_or_keywords.split(',') if item.strip()]
            
            if items:
                # 타입별로 다른 표현 사용
                if store_entity.type == 2:  # 콘텐츠
                    if len(items) > 1:
                        keyword_sentence = f"주요 키워드는 {', '.join(items[:-1])}, {items[-1]} 등입니다."
                    else:
                        keyword_sentence = f"주요 키워드는 {items[0]} 등입니다."
                else:  # 음식점(0), 카페(1)
                    if len(items) > 1:
                        keyword_sentence = f"주요 메뉴는 {', '.join(items[:-1])}, {items[-1]} 등이 있습니다."
                    else:
                        keyword_sentence = f"주요 메뉴는 {items[0]} 등이 있습니다."
                
                doc_parts.append(keyword_sentence)
        
        # 문장들을 공백으로 연결
        document = " ".join(doc_parts)
        
        return document
    
    def create_metadata(self, store_entity) -> dict:
        """
        메타데이터 생성 (구, 타입, 매장ID, 영업시간 포함)
        
        Args:
            store_entity: CategoryEntity 객체
            
        Returns:
            dict: 메타데이터
        """
        # 타입을 한글로 변환
        type_korean = self.convert_type_to_korean(store_entity.type)
        
        # 구 (지역)
        region = store_entity.gu if store_entity.gu else "정보없음"
        
        # 영업시간
        business_hour = store_entity.business_hour if store_entity.business_hour else "정보없음"
        
        metadata = {
            "store_id": store_entity.id,      # 매장ID
            "region": region,                 # 구 (필터링용)
            "type": type_korean,              # 타입 (한글)
            "type_code": str(store_entity.type),  # 타입 코드 (필터링용)
            "business_hour": business_hour    # 영업시간
        }
        
        return metadata
    
    async def load_all_stores(self, batch_size: int = 100):
        """
        DB의 모든 매장 데이터를 ChromaDB에 적재
        
        Args:
            batch_size: 배치 크기 (한 번에 처리할 매장 수)
        """
        logger.info("ChromaDB 데이터 적재 시작...")
        
        # Repository 초기화
        category_repo = CategoryRepository()
        category_tags_repo = CategoryTagsRepository()
        tags_repo = TagsRepository()
        
        # 전체 매장 데이터 조회
        stores = await category_repo.select()
        total_stores = len(stores)
        
        logger.info(f"총 {total_stores}개 매장 데이터 조회 완료")
        
        # 배치 처리
        success_count = 0
        fail_count = 0
        
        for i in range(0, total_stores, batch_size):
            batch = stores[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_stores + batch_size - 1) // batch_size
            
            logger.info(f"배치 {batch_num}/{total_batches} 처리 중...")
            
            documents = []
            metadatas = []
            ids = []
            
            for store in batch:
                try:
                    store_id = store.id
                    
                    # 매장별 태그 정보 조회
                    category_tags = await category_tags_repo.select(
                        category_id=store_id
                    )
                    
                    # 태그 상세 정보 가져오기
                    tag_details = []
                    for ct in category_tags:
                        tag_id = ct.tag_id if hasattr(ct, 'tag_id') else ct['tag_id']
                        tags = await tags_repo.select(id=tag_id)
                        
                        if tags and len(tags) > 0:
                            tag = tags[0]
                            tag_name = tag.name if hasattr(tag, 'name') else tag['name']
                            count = ct.count if hasattr(ct, 'count') else ct['count']
                            
                            tag_details.append({
                                'name': tag_name,
                                'count': count
                            })
                    
                    # 문서 생성 (구, 타입, 매장ID, 영업시간 제외)
                    doc = self.create_store_document(store, tag_details)
                    
                    # 메타데이터 생성 (구, 타입, 매장ID, 영업시간 포함)
                    metadata = self.create_metadata(store)
                    
                    documents.append(doc)
                    metadatas.append(metadata)
                    ids.append(str(store_id))
                    
                    success_count += 1
                    
                except Exception as e:
                    fail_count += 1
                    store_name = getattr(store, 'name', 'Unknown')
                    logger.error(f"매장 '{store_name}' 처리 중 오류: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
            
            # ChromaDB에 배치 추가
            if documents:
                try:
                    self.store_collection.add(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                    logger.info(f"배치 {batch_num}/{total_batches} 적재 완료: {len(documents)}개 매장")
                except Exception as e:
                    logger.error(f"ChromaDB 배치 추가 중 오류: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    fail_count += len(documents)
                    success_count -= len(documents)
        
        logger.info(f"ChromaDB 데이터 적재 완료!")
        logger.info(f"성공: {success_count}개, 실패: {fail_count}개")
        
        return success_count, fail_count
    
    async def load_single_store(self, store_id: str):
        """
        단일 매장 데이터를 ChromaDB에 적재 (업데이트용)
        
        Args:
            store_id: 매장 ID
            
        Returns:
            bool: 성공 여부
        """
        try:
            # Repository 초기화
            category_repo = CategoryRepository()
            category_tags_repo = CategoryTagsRepository()
            tags_repo = TagsRepository()
            
            # 매장 데이터 조회
            stores = await category_repo.select(id=store_id)
            if not stores or len(stores) == 0:
                logger.error(f"매장 ID '{store_id}'를 찾을 수 없습니다.")
                return False
            
            store = stores[0]
            
            # 태그 정보 조회
            category_tags = await category_tags_repo.select(
                category_id=store_id
            )
            
            tag_details = []
            for ct in category_tags:
                tag_id = ct.tag_id if hasattr(ct, 'tag_id') else ct['tag_id']
                tags = await tags_repo.select(id=tag_id)
                
                if tags and len(tags) > 0:
                    tag = tags[0]
                    tag_name = tag.name if hasattr(tag, 'name') else tag['name']
                    count = ct.count if hasattr(ct, 'count') else ct['count']
                    
                    tag_details.append({
                        'name': tag_name,
                        'count': count
                    })
            
            # 문서 생성 (구, 타입, 매장ID, 영업시간 제외)
            doc = self.create_store_document(store, tag_details)
            
            # 메타데이터 생성 (구, 타입, 매장ID, 영업시간 포함)
            metadata = self.create_metadata(store)
            
            # ChromaDB에 추가 (이미 있으면 업데이트)
            self.store_collection.upsert(
                documents=[doc],
                metadatas=[metadata],
                ids=[str(store_id)]
            )
            
            logger.info(f"매장 '{store.name}' ChromaDB 적재 완료")
            return True
            
        except Exception as e:
            logger.error(f"매장 ID '{store_id}' 적재 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def reset_collection(self):
        """
        컬렉션 초기화 (모든 데이터 삭제)
        주의: 이 메서드는 모든 데이터를 삭제합니다!
        """
        try:
            self.client.delete_collection(name="stores")
            logger.info("기존 'stores' 컬렉션 삭제 완료")
            
            # 임베딩 함수로 새 컬렉션 생성
            self.store_collection = self.client.create_collection(
                name="stores",
                metadata={"description": "매장 정보 검색용 컬렉션 (임베딩)"},
                embedding_function=self.embedding_function
            )
            logger.info("새로운 'stores' 컬렉션 생성 완료")
            
        except Exception as e:
            logger.error(f"컬렉션 초기화 중 오류: {e}")
    
    def get_collection_info(self) -> dict:
        """
        컬렉션 정보 조회
        
        Returns:
            dict: 컬렉션 통계 정보
        """
        try:
            count = self.store_collection.count()
            
            info = {
                "collection_name": self.store_collection.name,
                "total_documents": count,
                "metadata": self.store_collection.metadata,
                "embedding_model": "intfloat/multilingual-e5-large"
            }
            
            return info
            
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 중 오류: {e}")
            return {}