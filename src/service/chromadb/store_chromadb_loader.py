"""
ChromaDB 데이터 적재 모듈
매장 정보를 키워드 중심 문서로 저장합니다.
"""
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict, Set
import torch
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
        
        # GPU 사용 가능 여부 확인
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"사용 중인 디바이스: {self.device}")
        
        if self.device == "cuda":
            logger.info(f"GPU 이름: {torch.cuda.get_device_name(0)}")
            logger.info(f"GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 임베딩 모델 설정 (GPU 지원)
        logger.info("임베딩 모델 로딩 중: intfloat/multilingual-e5-large")
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="intfloat/multilingual-e5-large",
            device=self.device  # GPU 사용 설정
        )
        logger.info(f"임베딩 모델 로딩 완료 (디바이스: {self.device})")
        
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
        키워드 중심 문서 생성 (카테고리 + 메뉴 + 태그)
        """
        # 태그 처리 (상위 10개, 1등 제외)
        sorted_tags = sorted(tags, key=lambda x: x['count'], reverse=True)
        top_tags = sorted_tags[1:11]  # 2~11위
        tags_list = [tag['name'] for tag in top_tags]
        
        # 메뉴 (실제 음식명만)
        menu_items = []
        if store_entity.menu:
            menu_items = [item.strip() for item in store_entity.menu.split(',') if item.strip()]
        
        # 카테고리
        sub_categories = []
        if store_entity.sub_category:
            sub_categories = [cat.strip() for cat in store_entity.sub_category.split(',') if cat.strip()]
        
        doc_parts = []
        
        # 🔥 1순위: 카테고리 (3번 반복)
        if sub_categories:
            category_text = " ".join(sub_categories)
            doc_parts.append(f"{category_text} {category_text} {category_text}")
        
        # 2순위: 메뉴 (2번 반복)
        if menu_items:
            menu_text = " ".join(menu_items)
            doc_parts.append(f"{menu_text} {menu_text}")
        
        # 🔥 3순위: 태그 (속성 키워드 포함, 2번 반복)
        if tags_list:
            tags_text = " ".join(tags_list)
            doc_parts.append(f"{tags_text} {tags_text}")
        
        # 4순위: 매장명 (콘텐츠 타입만)
        if store_entity.type == 2 and store_entity.name:
            doc_parts.append(store_entity.name)
        
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
    
    def get_existing_store_ids(self) -> Set[str]:
        """
        ChromaDB에 현재 저장된 모든 매장 ID 조회
        
        Returns:
            Set[str]: 매장 ID 집합
        """
        try:
            # 전체 데이터 조회
            result = self.store_collection.get()
            existing_ids = set(result['ids']) if result and 'ids' in result else set()
            logger.info(f"ChromaDB에 현재 저장된 매장 수: {len(existing_ids)}개")
            return existing_ids
        except Exception as e:
            logger.error(f"기존 매장 ID 조회 중 오류: {e}")
            return set()
    
    def delete_stores(self, store_ids: List[str]):
        """
        특정 매장들을 ChromaDB에서 삭제
        
        Args:
            store_ids: 삭제할 매장 ID 리스트
        """
        if not store_ids:
            return
        
        try:
            self.store_collection.delete(ids=store_ids)
            logger.info(f"{len(store_ids)}개 매장 삭제 완료")
        except Exception as e:
            logger.error(f"매장 삭제 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def load_all_stores(self, batch_size: int = 100):
        """
        DB의 모든 매장 데이터를 ChromaDB에 적재 (upsert 방식)
        적재되지 않은 기존 데이터는 자동으로 삭제
        
        Args:
            batch_size: 배치 크기 (한 번에 처리할 매장 수)
        """
        logger.info("ChromaDB 데이터 적재 시작...")
        logger.info(f"GPU 사용 여부: {self.device == 'cuda'}")
        
        # 기존 ChromaDB에 저장된 매장 ID 조회
        existing_ids = self.get_existing_store_ids()
        
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
        insert_count = 0
        update_count = 0
        processed_ids = set()  # 적재된 매장 ID 추적
        
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
                    store_id = str(store.id)
                    
                    # 매장별 태그 정보 조회
                    category_tags = await category_tags_repo.select(
                        category_id=store.id
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
                    ids.append(store_id)
                    processed_ids.add(store_id)  # 처리된 ID 기록
                    
                    # 신규 삽입인지 업데이트인지 체크
                    if store_id in existing_ids:
                        update_count += 1
                    else:
                        insert_count += 1
                    
                    success_count += 1
                    
                except Exception as e:
                    fail_count += 1
                    store_name = getattr(store, 'name', 'Unknown')
                    logger.error(f"매장 '{store_name}' 처리 중 오류: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
            
            # ChromaDB에 배치 upsert (있으면 업데이트, 없으면 삽입)
            if documents:
                try:
                    self.store_collection.upsert(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                    logger.info(f"배치 {batch_num}/{total_batches} 적재 완료: {len(documents)}개 매장")
                except Exception as e:
                    logger.error(f"ChromaDB 배치 upsert 중 오류: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    fail_count += len(documents)
                    success_count -= len(documents)
                    # 실패한 ID들은 processed_ids에서 제거
                    for doc_id in ids:
                        processed_ids.discard(doc_id)
                        if doc_id in existing_ids:
                            update_count -= 1
                        else:
                            insert_count -= 1
        
        # 적재되지 않은 기존 데이터 삭제
        ids_to_delete = existing_ids - processed_ids
        delete_count = 0
        
        if ids_to_delete:
            logger.info(f"적재되지 않은 {len(ids_to_delete)}개 매장을 삭제합니다...")
            self.delete_stores(list(ids_to_delete))
            delete_count = len(ids_to_delete)
        
        logger.info(f"ChromaDB 데이터 적재 완료!")
        logger.info(f"성공: {success_count}개 (신규: {insert_count}개, 업데이트: {update_count}개)")
        logger.info(f"실패: {fail_count}개")
        logger.info(f"삭제: {delete_count}개")
        
        return {
            'success': success_count,
            'fail': fail_count,
            'insert': insert_count,
            'update': update_count,
            'delete': delete_count
        }
    
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
                "embedding_model": "intfloat/multilingual-e5-large",
                "device": self.device
            }
            
            return info
            
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 중 오류: {e}")
            return {}