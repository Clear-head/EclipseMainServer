"""
ChromaDB 데이터 적재 모듈
매장 정보를 ChromaDB에 저장하는 기능을 제공합니다.
한국어 임베딩 모델 사용
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
    """매장 데이터를 ChromaDB에 적재하는 클래스 (한국어 최적화)"""
    
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
        
        # 한국어 임베딩 모델 설정
        logger.info("한국어 임베딩 모델 로딩 중: jhgan/ko-sroberta-multitask")
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        logger.info("한국어 임베딩 모델 로딩 완료")
        
        # 컬렉션 생성 (한국어 임베딩 함수 적용)
        self.store_collection = self.client.get_or_create_collection(
            name="stores",
            metadata={"description": "매장 정보 및 태그 기반 검색용 컬렉션 (한국어 임베딩)"},
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
        매장 데이터를 임베딩용 텍스트 문서로 변환
        (매장ID, 타입, 지역, 태그, 영업시간, 메뉴만 포함)
        
        Args:
            store_entity: CategoryEntity 객체
            tags: 태그 목록 [{'name': '태그명', 'count': 개수}, ...]
            
        Returns:
            str: 임베딩용 텍스트 문서
        """
        # 타입을 한글로 변환
        type_korean = self.convert_type_to_korean(store_entity.type)
        
        # 지역 (구)
        region = store_entity.gu or ''
        
        # 태그를 count 기준으로 정렬 (중요도 반영)
        sorted_tags = sorted(tags, key=lambda x: x['count'], reverse=True)
        
        # count가 높은 태그일수록 여러 번 반복해서 가중치 부여
        tag_texts = []
        for tag in sorted_tags:
            tag_name = tag['name']
            tag_count = tag['count']
            # count가 높을수록 반복 (최대 5번)
            repeat_count = min(tag_count // 10 + 1, 5)
            tag_texts.extend([tag_name] * repeat_count)
        
        tags_string = ", ".join(tag_texts) if tag_texts else ""
        
        # 영업시간
        business_hour = store_entity.business_hour or ''
        
        # 메뉴
        menu = store_entity.menu or ''
        
        # 임베딩용 문서 생성 (6가지 필드만)
        document = f"""
매장ID: {store_entity.id}
타입: {type_korean}
지역: {region}
태그: {tags_string}
영업시간: {business_hour}
메뉴: {menu}
        """.strip()
        
        return document
    
    def create_metadata(self, store_entity) -> dict:
        """
        메타데이터 생성 (매장ID, 타입만 저장)
        
        Args:
            store_entity: CategoryEntity 객체
            
        Returns:
            dict: 메타데이터
        """
        # 타입을 한글로 변환
        type_korean = self.convert_type_to_korean(store_entity.type)
        
        metadata = {
            "store_id": store_entity.id,
            "type": type_korean,
            "type_code": str(store_entity.type)  # 필터링용
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
        stores = await category_repo.select_by()
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
                    store_name = store.name
                    
                    # 매장별 태그 정보 조회
                    category_tags = await category_tags_repo.select_by(
                        category_id=store_id
                    )
                    
                    # 태그 상세 정보 가져오기
                    tag_details = []
                    for ct in category_tags:
                        tag_id = ct.tag_id if hasattr(ct, 'tag_id') else ct['tag_id']
                        tags = await tags_repo.select_by(id=tag_id)
                        
                        if tags and len(tags) > 0:
                            tag = tags[0]
                            tag_name = tag.name if hasattr(tag, 'name') else tag['name']
                            count = ct.count if hasattr(ct, 'count') else ct['count']
                            
                            tag_details.append({
                                'name': tag_name,
                                'count': count
                            })
                    
                    # 문서 및 메타데이터 생성
                    doc = self.create_store_document(store, tag_details)
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
            stores = await category_repo.select_by(id=store_id)
            if not stores or len(stores) == 0:
                logger.error(f"매장 ID '{store_id}'를 찾을 수 없습니다.")
                return False
            
            store = stores[0]
            
            # 태그 정보 조회
            category_tags = await category_tags_repo.select_by(
                category_id=store_id
            )
            
            tag_details = []
            for ct in category_tags:
                tag_id = ct.tag_id if hasattr(ct, 'tag_id') else ct['tag_id']
                tags = await tags_repo.select_by(id=tag_id)
                
                if tags and len(tags) > 0:
                    tag = tags[0]
                    tag_name = tag.name if hasattr(tag, 'name') else tag['name']
                    count = ct.count if hasattr(ct, 'count') else ct['count']
                    
                    tag_details.append({
                        'name': tag_name,
                        'count': count
                    })
            
            # 문서 및 메타데이터 생성
            doc = self.create_store_document(store, tag_details)
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
            
            # 한국어 임베딩 함수로 새 컬렉션 생성
            self.store_collection = self.client.create_collection(
                name="stores",
                metadata={"description": "매장 정보 및 태그 기반 검색용 컬렉션 (한국어 임베딩)"},
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
                "embedding_model": "jhgan/ko-sroberta-multitask"
            }
            
            return info
            
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 중 오류: {e}")
            return {}