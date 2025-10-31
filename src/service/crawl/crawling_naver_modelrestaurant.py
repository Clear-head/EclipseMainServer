"""
서울시 각 구 API 모범음식점 데이터 크롤링 모듈 (메모리 최적화 + 봇 우회 + 병렬 처리)
"""
import asyncio
from playwright.async_api import async_playwright, Page
import sys, os
from dotenv import load_dotenv

load_dotenv(dotenv_path="src/.env")

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.logger.custom_logger import get_logger

# 외부 API 서비스 import
from src.infra.external.seoul_district_api_service import SeoulDistrictAPIService

# 공통 모듈 import
from src.service.crawl.utils.optimized_browser_manager import OptimizedBrowserManager
from src.service.crawl.utils.human_like_actions import HumanLikeActions
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.search_strategy import NaverMapSearchStrategy
from src.service.crawl.utils.crawling_manager import CrawlingManager


class NaverMapDistrictCrawler:
    """서울시 각 구 API 데이터 크롤링 클래스 (병렬 처리)"""
    
    RESTART_INTERVAL = 50  # 50개마다 컨텍스트 재시작
    
    def __init__(self, district_name: str, headless: bool = False):
        self.district_name = district_name
        self.headless = headless
        self.logger = get_logger(__name__)
        self.data_saver = StoreDataSaver()
        self.search_strategy = NaverMapSearchStrategy()
        self.human_actions = HumanLikeActions()
        self.success_count = 0
        self.fail_count = 0
    
    async def crawl_district_api(self, delay: int = 20):
        """
        해당 구의 API에서 데이터를 가져와 병렬 크롤링
        
        Args:
            delay: 크롤링 간 기본 딜레이 (초)
        """
        # 1단계: API에서 데이터 가져오기
        api_service = SeoulDistrictAPIService(self.district_name)
        api_data = await api_service.fetch_all_restaurants()
        
        if not api_data:
            self.logger.warning(f"{self.district_name} API에서 데이터를 가져올 수 없습니다.")
            return
        
        stores = api_service.convert_to_store_format(api_data)
        total = len(stores)
        
        self.logger.info(f"{self.district_name} 총 {total}개 매장 크롤링 시작 (병렬 처리)")
        self.logger.info(f"배치 크기: {self.RESTART_INTERVAL}개")
        self.logger.info(f"예상 배치 수: {(total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL}개")
        
        # 2단계: 배치 단위로 병렬 크롤링
        async with async_playwright() as p:
            browser = await OptimizedBrowserManager.create_optimized_browser(p, self.headless)
            
            try:
                for batch_start in range(0, total, self.RESTART_INTERVAL):
                    batch_end = min(batch_start + self.RESTART_INTERVAL, total)
                    batch = stores[batch_start:batch_end]
                    
                    batch_num = batch_start // self.RESTART_INTERVAL + 1
                    total_batches = (total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL
                    
                    self.logger.info(f"[{self.district_name}] 배치 {batch_num}/{total_batches}: {batch_start+1}~{batch_end}/{total}")
                    
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
                            rest_time = random.uniform(20, 40)
                            self.logger.info(f"배치 {batch_num} 완료, {rest_time:.0f}초 휴식...\n")
                            await asyncio.sleep(rest_time)
                
                # 최종 결과
                self.logger.info(f"{self.district_name} 크롤링 완료!")
                self.logger.info(f"총 처리: {total}개")
                self.logger.info(f"성공: {self.success_count}개")
                self.logger.info(f"실패: {self.fail_count}개")
                if total > 0:
                    self.logger.info(f"성공률: {self.success_count/total*100:.1f}%")
                
            except Exception as e:
                self.logger.error(f"{self.district_name} 크롤링 중 오류: {e}")
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
            # ========================================
            # 🔥 병렬 처리: CrawlingManager 사용
            # ========================================
            crawling_manager = CrawlingManager(self.district_name)
            
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
        단일 매장 크롤링 (병렬용)
        
        Returns:
            Tuple: (store_data, name) 또는 None
        """
        store_name = store['name']
        store_address = store['address']
        road_address = store['road_address']
        
        try:
            # 검색 전략 사용
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
                log_prefix=self.district_name
            )
        
        return wrapper


async def main():
    """메인 함수"""
    logger = get_logger(__name__)
    
    # 크롤링할 구 선택
    districts_to_crawl = [
        '강남구', '강동구', '강북구', '강서구', '관악구',
        '광진구', '구로구', '금천구', '노원구', '도봉구',
        '동대문구', '동작구', '마포구', '서대문구', '서초구',
        '성동구', '성북구', '송파구', '양천구', '영등포구',
        '용산구', '은평구', '종로구', '중구', '중랑구'
    ]
    
    headless_mode = False
    delay_seconds = 15
    
    logger.info("서울시 구청 API 크롤러 시작 (병렬 처리)")
    logger.info(f"대상 구: 총 {len(districts_to_crawl)}개")
    
    for idx, district_name in enumerate(districts_to_crawl, 1):
        try:
            logger.info(f"[{idx}/{len(districts_to_crawl)}] {district_name} 시작")
            
            crawler = NaverMapDistrictCrawler(
                district_name=district_name,
                headless=headless_mode
            )
            
            await crawler.crawl_district_api(delay=delay_seconds)
            
            logger.info(f"[{idx}/{len(districts_to_crawl)}] {district_name} 완료")
            
            # 다음 구로 넘어가기 전 대기
            if idx < len(districts_to_crawl):
                import random
                wait_time = random.uniform(40, 60)
                logger.info(f"다음 구 크롤링 전 {wait_time:.0f}초 대기...\n")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            logger.error(f"{district_name} 크롤링 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            if idx < len(districts_to_crawl):
                logger.info(f"다음 구({districts_to_crawl[idx]})로 계속 진행합니다...\n")
                await asyncio.sleep(30)
    
    logger.info("모든 구 크롤링 완료!")