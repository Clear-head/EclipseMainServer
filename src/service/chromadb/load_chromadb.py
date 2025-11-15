"""
ChromaDB 데이터 적재 실행 스크립트
DB에 저장된 매장 데이터를 ChromaDB에 별도로 적재합니다.
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.service.chromadb.store_chromadb_loader import StoreChromaDBLoader
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


async def main():
    """메인 실행 함수"""
    logger.info("ChromaDB 데이터 적재 시작")
    
    # ChromaDB 로더 초기화 (임베딩 모델 로딩)
    loader = StoreChromaDBLoader(persist_directory="./chroma_db")
    
    # 전체 매장 데이터 적재 (upsert 방식)
    logger.info("매장 데이터를 ChromaDB에 적재합니다...")
    logger.info("(기존 데이터는 업데이트, 신규 데이터는 삽입, 삭제된 데이터는 제거)")
    
    result = await loader.load_all_stores(batch_size=100)
    
    # 결과 출력
    logger.info("적재 완료!")
    logger.info(f"성공: {result['success']}개")
    logger.info(f"  - 신규 삽입: {result['insert']}개")
    logger.info(f"  - 업데이트: {result['update']}개")
    logger.info(f"실패: {result['fail']}개")
    logger.info(f"삭제: {result['delete']}개")
    
    # 컬렉션 정보 출력
    info = loader.get_collection_info()
    logger.info("ChromaDB 컬렉션 정보:")
    logger.info(f"  - 컬렉션명: {info.get('collection_name', 'N/A')}")
    logger.info(f"  - 총 문서 수: {info.get('total_documents', 0)}개")
    logger.info(f"  - 임베딩 모델: {info.get('embedding_model', 'N/A')}")
    logger.info(f"  - 디바이스: {info.get('device', 'N/A')}")
    logger.info(f"  - 메타데이터: {info.get('metadata', {})}")