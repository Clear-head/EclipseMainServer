"""
크롤링 작업 실행 모듈
모든 크롤링을 순차적으로 실행하고 ChromaDB에 적재
"""
import asyncio
from datetime import datetime
from src.logger.custom_logger import get_logger
from src.infra.database.repository.category_repository import CategoryRepository
from src.service.chromadb.store_chromadb_loader import StoreChromaDBLoader

import src.service.crawl.crawling_naver_modelrestaurant
import src.service.crawl.crawling_naver_list
import src.service.crawl.crawling_bluer
import src.service.crawl.crawling_naver_contents
import src.service.crawl.crawling_diningcode
import src.service.crawl.crawling_laborers_spot

logger = get_logger(__name__)


async def run_crawling_job():
    """
    크롤링 작업 실행
    1. 크롤링 시작 시간 기록
    2. 모든 크롤러 순차 실행
    3. ChromaDB 적재
    4. 오래된 매장 데이터 정리
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
    
    # 1. 모든 크롤러 순차 실행
    crawlers = [
        {
            "name": "공사맛집",
            "func": src.service.crawl.crawling_laborers_spot.main,
            "args": []
        },
        {
            "name": "다이닝코드",
            "func": src.service.crawl.crawling_diningcode.main,
            "args": []
        },
        {
            "name": "서울,가보자고",
            "func": src.service.crawl.crawling_naver_list.main,
            "args": ["https://map.naver.com/p/favorite/sharedPlace/folder/1fea0b9f6dd7481180a819f07e352e2d/pc?c=11.00,0,0,0,dh"]
        },
        {
            "name": "레드리본",
            "func": src.service.crawl.crawling_naver_list.main,
            "args": ["https://map.naver.com/p/favorite/sharedPlace/folder/723cd582cd1e43dcac5234ad055c7494/pc?c=10.00,0,0,0,dh"]
        },
        {
            "name": "블루리본 디저트베이커리",
            "func": src.service.crawl.crawling_naver_list.main,
            "args": ["https://map.naver.com/p/favorite/sharedPlace/folder/a5b889b0ec9d4bafa6156d25cde3fedd/pc?c=6.00,0,0,0,dh"]
        },
        {
            "name": "모범음식점",
            "func": src.service.crawl.crawling_naver_modelrestaurant.main,
            "args": []
        },
        {
            "name": "삼성생명 인생카페",
            "func": src.service.crawl.crawling_bluer.main,
            "args": []
        },
        {
            "name": "서울의 콘텐츠",
            "func": src.service.crawl.crawling_naver_contents.main,
            "args": []
        }
    ]
    
    for crawler in crawlers:
        try:
            logger.info("-" * 60)
            logger.info(f"{crawler['name']} 크롤링 시작")
            logger.info("-" * 60)
            
            crawler_start = datetime.now()
            
            # 크롤러 실행
            if crawler['args']:
                await crawler['func'](*crawler['args'])
            else:
                await crawler['func']()
            
            crawler_end = datetime.now()
            duration = (crawler_end - crawler_start).total_seconds()
            
            logger.info(f"{crawler['name']} 완료 (소요시간: {duration:.2f}초)\n")
            
            crawling_results["crawlers"].append({
                "name": crawler['name'],
                "status": "success",
                "duration": duration
            })
            crawling_results["success_count"] += 1
            
        except Exception as e:
            logger.error(f"{crawler['name']} 크롤링 실패: {e}")
            crawling_results["crawlers"].append({
                "name": crawler['name'],
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
    
    # 2. 오래된 매장 데이터 정리
    try:
        logger.info("\n오래된 매장 데이터 정리 시작...")
        deleted_count = await cleanup_old_stores(crawling_start_time)
        logger.info(f"오래된 매장 {deleted_count}개 삭제 완료\n")
        crawling_results["deleted_count"] = deleted_count
    except Exception as e:
        logger.error(f"오래된 매장 데이터 정리 실패: {e}")
        crawling_results["deleted_count"] = 0
    
    # 3. ChromaDB 적재
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
    
    # 4. 최종 결과 요약
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
    
    if "chromadb" in crawling_results and "success" in crawling_results["chromadb"]:
        chroma = crawling_results["chromadb"]
        logger.info(f"ChromaDB 적재: {chroma['success']}개 (신규: {chroma['insert']}, 업데이트: {chroma['update']})")
    
    logger.info("=" * 80 + "\n")
    
    return crawling_results


async def cleanup_old_stores(crawling_start_time: datetime) -> int:
    """
    크롤링 시작 시점 이전의 last_crawl을 가진 매장 삭제
    
    Args:
        crawling_start_time: 크롤링 시작 시간
    
    Returns:
        int: 삭제된 매장 수
    """
    try:
        from src.service.crawl.delete_crawled import delete_category, delete_category_tags
        
        repository = CategoryRepository()
        
        # 모든 매장 조회
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