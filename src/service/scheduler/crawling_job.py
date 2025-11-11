"""
크롤링 작업 실행 모듈 (JSON 기반)
- src/resources/crawl/crawlers.json 을 읽어 크롤러 목록을 구성
- 각 크롤러를 순차 실행
- 크롤링 시작 시점 이전 last_crawl 을 가진 매장은 삭제
- ChromaDB 적재 실행
"""
import importlib
import inspect
from datetime import datetime
from typing import List, Dict

from src.infra.database.repository.category_repository import CategoryRepository
from src.logger.custom_logger import get_logger
from src.service.chromadb.store_chromadb_loader import StoreChromaDBLoader
from src.utils.crawlers_loader import load_json_resource

logger = get_logger(__name__)


def _load_crawlers_from_config() -> List[Dict]:
    cfg = load_json_resource("crawlers.json")
    crawlers = cfg.get("crawlers", []) if isinstance(cfg, dict) else []
    if not crawlers:
        logger.warning("크롤러 설정이 비어있습니다: src/resources/crawl/crawlers.json")
    return crawlers


async def _call_crawler(module_path: str, func_name: str = "main", args: List = None):
    """
    모듈 동적 임포트 후 함수 호출. coroutine이면 await, 아니면 실행 결과가 coroutine이면 await 처리.
    """
    args = args or []
    try:
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name)
    except Exception as e:
        raise ImportError(f"모듈/함수 로드 실패: {module_path}.{func_name} - {e}")

    # coroutine function 인가?
    if inspect.iscoroutinefunction(func):
        return await func(*args)
    else:
        # 일반 함수일 수 있으니 호출 결과가 coroutine이면 await
        result = func(*args)
        if inspect.isawaitable(result):
            return await result
        return result


async def run_crawling_job():
    """
    JSON으로부터 크롤러 목록을 불러와 순차 실행하고 ChromaDB 적재 및 오래된 매장 삭제 수행
    """
    crawling_start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(f"크롤링 작업 시작: {crawling_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    crawling_results = {
        "start_time": crawling_start_time,
        "crawlers": [],
        "success_count": 0,
        "fail_count": 0
    }

    crawlers = _load_crawlers_from_config()

    for entry in crawlers:
        name = entry.get("name", f"{entry.get('module')}::{entry.get('function','main')}")
        module_path = entry.get("module")
        func_name = entry.get("function", "main")
        args = entry.get("args", [])

        logger.info("-" * 60)
        logger.info(f"{name} 크롤링 시작")
        logger.info("-" * 60)

        crawler_start = datetime.now()
        try:
            await _call_crawler(module_path, func_name, args)
            crawler_end = datetime.now()
            duration = (crawler_end - crawler_start).total_seconds()

            logger.info(f"{name} 완료 (소요시간: {duration:.2f}초)\n")
            crawling_results["crawlers"].append({
                "name": name,
                "status": "success",
                "duration": duration
            })
            crawling_results["success_count"] += 1

        except Exception as e:
            logger.error(f"{name} 크롤링 실패: {e}")
            crawling_results["crawlers"].append({
                "name": name,
                "status": "failed",
                "error": str(e)
            })
            crawling_results["fail_count"] += 1

    crawling_end_time = datetime.now()
    total_crawling_time = (crawling_end_time - crawling_start_time).total_seconds()

    logger.info("=" * 80)
    logger.info(f"모든 크롤링 완료 (총 소요시간: {total_crawling_time:.2f}초)")
    logger.info(f"성공: {crawling_results['success_count']}개, 실패: {crawling_results['fail_count']}개")
    logger.info("=" * 80)

    # 오래된 매장 삭제 (크롤링 시작 시점 이전 last_crawl)
    try:
        logger.info("\n오래된 매장 데이터 정리 시작...")
        deleted_count = await cleanup_old_stores(crawling_start_time)
        logger.info(f"오래된 매장 {deleted_count}개 삭제 완료\n")
        crawling_results["deleted_count"] = deleted_count
    except Exception as e:
        logger.error(f"오래된 매장 데이터 정리 실패: {e}")
        crawling_results["deleted_count"] = 0

    # ChromaDB 적재
    try:
        logger.info("=" * 80)
        logger.info("ChromaDB 데이터 적재 시작")
        logger.info("=" * 80)

        loader = StoreChromaDBLoader(persist_directory="./chroma_db")
        result = await loader.load_all_stores(batch_size=100)

        logger.info("=" * 80)
        logger.info("ChromaDB 적재 완료!")
        logger.info(f"성공: {result['success']}개 (신규: {result['insert']}개, 업데이트: {result['update']}개)")
        logger.info(f"실패: {result['fail']}개")
        logger.info(f"삭제: {result['delete']}개")
        logger.info("=" * 80)

        crawling_results["chromadb"] = result

    except Exception as e:
        logger.error(f"ChromaDB 적재 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        crawling_results["chromadb"] = {"error": str(e)}

    # 요약 로그
    end_time = datetime.now()
    total_time = (end_time - crawling_start_time).total_seconds()

    logger.info("\n" + "=" * 80)
    logger.info("크롤링 작업 최종 결과")
    logger.info("=" * 80)
    logger.info(f"시작 시간: {crawling_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"총 소요 시간: {total_time:.2f}초 ({total_time/60:.2f}분)")
    logger.info(f"크롤러 성공: {crawling_results['success_count']}개")
    logger.info(f"크롤러 실패: {crawling_results['fail_count']}개")
    logger.info(f"오래된 매장 삭제: {crawling_results.get('deleted_count', 0)}개")

    if "chromadb" in crawling_results and isinstance(crawling_results["chromadb"], dict) and "success" in crawling_results["chromadb"]:
        chroma = crawling_results["chromadb"]
        logger.info(f"ChromaDB 적재: {chroma['success']}개 (신규: {chroma['insert']}, 업데이트: {chroma['update']})")

    logger.info("=" * 80 + "\n")

    return crawling_results


async def cleanup_old_stores(crawling_start_time: datetime) -> int:
    """
    크롤링 시작 시점 이전의 last_crawl을 가진 매장 삭제
    """
    try:
        from src.service.crawl.delete_crawled import delete_category, delete_category_tags

        repository = CategoryRepository()

        all_stores = await repository.select()

        stores_to_delete = []

        for store in all_stores:
            # last_crawl이 크롤링 시작 시점 이전인 경우
            if store.last_crawl and store.last_crawl < crawling_start_time:
                stores_to_delete.append(store)

        logger.info(f"삭제 대상 매장: {len(stores_to_delete)}개")

        deleted_count = 0

        for store in stores_to_delete:
            try:
                # 1. category_tags 먼저 삭제
                await delete_category_tags(store.id)

                # 2. category 삭제
                await delete_category(store.id)

                deleted_count += 1
                logger.info(f"매장 삭제 완료: {store.name} (ID: {store.id}, last_crawl: {store.last_crawl})")

            except Exception as e:
                logger.error(f"매장 삭제 실패: {store.name} (ID: {store.id}) - {e}")
                continue

        logger.info(f"총 {deleted_count}개 매장 삭제 완료")
        return deleted_count

    except Exception as e:
        logger.error(f"오래된 매장 정리 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0