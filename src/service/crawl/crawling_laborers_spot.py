"""
공공데이터포털 맛집 데이터 크롤링 모듈 (메모리 최적화 + 봇 우회 + 병렬 처리)
"""
import asyncio
from playwright.async_api import async_playwright, Page
import sys
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="src/.env")

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.logger.custom_logger import get_logger

# 외부 API 서비스 import
from src.infra.external.public_data_api_service import PublicDataAPIService

# 공통 모듈 import
from src.service.crawl.utils.optimized_browser_manager import OptimizedBrowserManager
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.search_strategy import NaverMapSearchStrategy
from src.service.crawl.utils.crawling_manager import CrawlingManager

logger = get_logger(__name__)


class NaverMapPublicDataCrawler:
    """공공데이터포털 맛집 데이터 크롤링 클래스 (병렬 처리)"""
    
    RESTART_INTERVAL = 50  # 50개마다 컨텍스트 재시작
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.logger = logger
        self.data_saver = StoreDataSaver()
        self.search_strategy = NaverMapSearchStrategy()
        self.success_count = 0
        self.fail_count = 0
    
    async def crawl_public_data(self, delay: int = 15):
        """
        공공데이터포털 API에서 서울특별시 데이터를 가져와 병렬 크롤링
        
        Args:
            delay: 크롤링 간 기본 딜레이 (초)
        """
        # 1단계: API에서 서울특별시 데이터만 가져오기
        api_service = PublicDataAPIService()
        seoul_data = await api_service.fetch_seoul_restaurants()
        
        if not seoul_data:
            self.logger.warning("서울특별시 맛집 데이터를 가져올 수 없습니다.")
            return
        
        # 2단계: 크롤링용 포맷으로 변환
        stores = api_service.convert_to_store_format(seoul_data)
        total = len(stores)
        
        self.logger.info(f"공공데이터 총 {total}개 서울특별시 맛집 크롤링 시작 (병렬 처리)")
        self.logger.info(f"배치 크기: {self.RESTART_INTERVAL}개")
        self.logger.info(f"예상 배치 수: {(total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL}개")
        
        # 3단계: 배치 단위로 병렬 크롤링
        async with async_playwright() as p:
            browser = await OptimizedBrowserManager.create_optimized_browser(p, self.headless)
            
            try:
                for batch_start in range(0, total, self.RESTART_INTERVAL):
                    batch_end = min(batch_start + self.RESTART_INTERVAL, total)
                    batch = stores[batch_start:batch_end]
                    
                    batch_num = batch_start // self.RESTART_INTERVAL + 1
                    total_batches = (total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL
                    
                    self.logger.info(f"[공공데이터] 배치 {batch_num}/{total_batches}: {batch_start+1}~{batch_end}/{total}")
                    
                    # 새 컨텍스트 생성
                    context = await OptimizedBrowserManager.create_stealth_context(browser)
                    page = await context.new_page()
                    
                    try:
                        await self._process_batch_parallel(
                            page, batch, batch_start, total, delay
                        )
                    except Exception as e:
                        self.logger.error(f"배치 {batch_num} 처리 중 오류: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())
                    finally:
                        await context.close()
                        await asyncio.sleep(3)
                        
                        # 배치 간 휴식
                        if batch_end < total:
                            import random
                            rest_time = random.uniform(30, 50)
                            self.logger.info(f"배치 {batch_num} 완료, {rest_time:.0f}초 휴식...\n")
                            await asyncio.sleep(rest_time)
                
                # 최종 결과
                self.logger.info(f"공공데이터 크롤링 완료!")
                self.logger.info(f"총 처리: {total}개")
                self.logger.info(f"성공: {self.success_count}개")
                self.logger.info(f"실패: {self.fail_count}개")
                if total > 0:
                    self.logger.info(f"성공률: {self.success_count/total*100:.1f}%")
                
            except Exception as e:
                self.logger.error(f"공공데이터 크롤링 중 오류: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                await browser.close()
    
    async def _process_batch_parallel(
        self, 
        page: Page, 
        batch: list, 
        batch_start: int, 
        total: int, 
        delay: int
    ):
        """배치 병렬 크롤링"""
        try:
            # 병렬 처리: CrawlingManager 사용
            crawling_manager = CrawlingManager("공공데이터")
            
            await crawling_manager.execute_crawling_with_save(
                stores=batch,
                crawl_func=lambda store, idx, t: self._crawl_single_store_parallel(page, store),
                save_func=self._save_wrapper_with_total(batch_start, total),
                delay=delay
            )
            
            # 성공/실패 카운트 업데이트
            self.success_count += crawling_manager.success_count
            self.fail_count += crawling_manager.fail_count
            
        except Exception as e:
            self.logger.error(f"배치 처리 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def _crawl_single_store_parallel(self, page: Page, store: dict):
        """
        단일 맛집 크롤링 (병렬용)
        
        Returns:
            Tuple: (store_data, name) 또는 None
        """
        store_name = store['name']
        store_address = store['address']
        road_address = store['road_address']
        
        try:
            # 검색 전략 사용 (도로명 주소 우선)
            async def extract_callback(entry_frame, page):
                extractor = StoreDetailExtractor(entry_frame, page)
                return await extractor.extract_all_details()
            
            store_data = await self.search_strategy.search_with_multiple_strategies(
                page=page,
                store_name=store_name,
                store_address=store_address,
                road_address=road_address,
                extractor_callback=extract_callback
            )
            
            if store_data:
                # 리소스 정리
                await OptimizedBrowserManager.clear_page_resources(page)
                return (store_data, store_name)
            
            return None
            
        except Exception as e:
            self.logger.error(f"'{store_name}' 크롤링 중 오류: {e}")
            return None
    
    def _save_wrapper_with_total(self, batch_start: int, total: int):
        """저장 래퍼 팩토리"""
        async def wrapper(idx: int, _, store_data_tuple, store_name: str):
            if store_data_tuple is None:
                return (False, "크롤링 실패")
            
            store_data, actual_name = store_data_tuple
            global_idx = batch_start + idx
            
            return await self.data_saver.save_store_data(
                idx=global_idx,
                total=total,
                store_data=store_data,
                store_name=actual_name,
                log_prefix="공공데이터"
            )
        
        return wrapper


async def main():
    """메인 함수"""
    logger.info("공공데이터포털 맛집 크롤러 시작 (병렬 처리)")
    
    headless_mode = False
    delay_seconds = 15
    
    crawler = NaverMapPublicDataCrawler(headless=headless_mode)
    await crawler.crawl_public_data(delay=delay_seconds)
    
    logger.info("공공데이터포털 크롤링 완료!")