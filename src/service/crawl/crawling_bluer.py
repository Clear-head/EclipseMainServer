"""
Bluer 웹사이트 음식점 크롤링 모듈 (메모리 최적화 + 봇 우회 + 병렬 처리)
1단계: 전체 목록 수집 → 2단계: 배치 병렬 크롤링
"""
import asyncio
from playwright.async_api import async_playwright, TimeoutError, Page
import sys, os
from dotenv import load_dotenv

load_dotenv(dotenv_path="src/.env")

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.logger.custom_logger import get_logger

# 공통 모듈 import
from src.service.crawl.utils.optimized_browser_manager import OptimizedBrowserManager
from src.service.crawl.utils.human_like_actions import HumanLikeActions
from src.service.crawl.utils.scroll_helper import PageNavigator
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.search_strategy import NaverMapSearchStrategy
from src.service.crawl.utils.crawling_manager import CrawlingManager


class BluerRestaurantCrawler:
    """Bluer 웹사이트 음식점 크롤링 클래스 (병렬 처리)"""
    
    RESTART_INTERVAL = 50  # 50개마다 컨텍스트 재시작
    
    def __init__(self, headless: bool = False):
        self.logger = get_logger(__name__)
        self.headless = headless
        self.bluer_url = "https://www.bluer.co.kr/search?query=&foodType=&foodTypeDetail=&feature=112&location=&locationDetail=&area=&areaDetail=&ribbonType=&priceRangeMin=0&priceRangeMax=1000&week=&hourMin=0&hourMax=48&year=&evaluate=&sort=&listType=card&isSearchName=false&isBrand=false&isAround=false&isMap=false&zone1=&zone2=&food1=&food2=&zone2Lat=&zone2Lng=&distance=1000&isMapList=false#restaurant-filter-bottom"
        self.data_saver = StoreDataSaver()
        self.search_strategy = NaverMapSearchStrategy()
        self.human_actions = HumanLikeActions()
        self.success_count = 0
        self.fail_count = 0
    
    async def crawl_all_pages(self, delay: int = 5, naver_delay: int = 20):
        """
        Bluer 전체 페이지 병렬 크롤링
        1단계: Bluer에서 전체 목록 수집 → 2단계: 네이버 지도에서 배치 병렬 크롤링
        
        Args:
            delay: Bluer 페이지 간 딜레이 (초)
            naver_delay: 네이버 지도 크롤링 딜레이 (초)
        """
        async with async_playwright() as p:
            # 1단계: Bluer에서 전체 음식점 목록 수집
            self.logger.info("1단계: Bluer 전체 목록 수집 시작")
            
            all_restaurants = await self._collect_all_restaurants(p, delay)
            
            if not all_restaurants:
                self.logger.warning("수집된 음식점이 없습니다.")
                return
            
            total = len(all_restaurants)
            self.logger.info(f"총 {total}개 음식점 수집 완료")
            
            # 2단계: 네이버 지도에서 배치 병렬 크롤링
            self.logger.info("2단계: 네이버 지도 병렬 크롤링 시작")
            self.logger.info(f"배치 크기: {self.RESTART_INTERVAL}개")
            self.logger.info(f"예상 배치 수: {(total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL}개")
            
            naver_browser = await OptimizedBrowserManager.create_optimized_browser(p, self.headless)
            
            try:
                for batch_start in range(0, total, self.RESTART_INTERVAL):
                    batch_end = min(batch_start + self.RESTART_INTERVAL, total)
                    batch = all_restaurants[batch_start:batch_end]
                    
                    batch_num = batch_start // self.RESTART_INTERVAL + 1
                    total_batches = (total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL
                    
                    self.logger.info(f"배치 {batch_num}/{total_batches}: {batch_start+1}~{batch_end}/{total}")
                    
                    # 새 컨텍스트 생성
                    context = await OptimizedBrowserManager.create_stealth_context(naver_browser)
                    page = await context.new_page()
                    
                    try:
                        await self._process_batch_parallel(
                            page, batch, batch_start, total, naver_delay
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
                self.logger.info(f"전체 크롤링 완료!")
                self.logger.info(f"총 처리: {total}개")
                self.logger.info(f"성공: {self.success_count}개")
                self.logger.info(f"실패: {self.fail_count}개")
                if total > 0:
                    self.logger.info(f"   성공률: {self.success_count/total*100:.1f}%")
                
            finally:
                await naver_browser.close()
    
    async def _collect_all_restaurants(self, playwright, delay: int) -> list:
        """Bluer에서 전체 음식점 목록만 수집"""
        browser = await playwright.chromium.launch(headless=self.headless)
        page = await browser.new_page()
        
        all_restaurants = []
        
        try:
            self.logger.info(f"Bluer 페이지 접속 중...")
            await page.goto(self.bluer_url, wait_until='networkidle')
            await asyncio.sleep(3)
            
            current_page = 1
            
            while True:
                self.logger.info(f"Bluer 페이지 {current_page} 수집 중...")
                
                restaurants = await self._extract_restaurants_from_page(page)
                
                if restaurants:
                    self.logger.info(f"페이지 {current_page}: {len(restaurants)}개 수집 (누적 {len(all_restaurants) + len(restaurants)}개)")
                    all_restaurants.extend(restaurants)
                else:
                    self.logger.warning(f"페이지 {current_page}에서 음식점을 찾지 못했습니다.")
                    break
                
                has_next = await PageNavigator.go_to_next_page_bluer(page)
                
                if not has_next:
                    self.logger.info(f"마지막 페이지 도달 (총 {current_page}페이지)")
                    break
                
                current_page += 1
                await asyncio.sleep(delay)
            
        except Exception as e:
            self.logger.error(f"Bluer 목록 수집 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            await browser.close()
        
        return all_restaurants
    
    async def _extract_restaurants_from_page(self, page: Page) -> list:
        """현재 페이지에서 음식점 이름과 주소 추출"""
        restaurants = []
        
        try:
            await page.wait_for_selector('#list-restaurant', timeout=10000)
            await asyncio.sleep(2)
            
            list_items = await page.locator('#list-restaurant > li').all()
            
            for idx, item in enumerate(list_items, 1):
                try:
                    # 음식점명
                    name_selector = 'div > header > div.header-title > div:nth-child(2) > h3'
                    name_element = item.locator(name_selector)
                    
                    if await name_element.count() > 0:
                        name = await name_element.inner_text(timeout=3000)
                        name = name.strip()
                    else:
                        continue
                    
                    # 주소
                    address_selector = 'div > div > div.info > div:nth-child(1) > div'
                    address_element = item.locator(address_selector)
                    
                    if await address_element.count() > 0:
                        address = await address_element.inner_text(timeout=3000)
                        address = address.strip()
                    else:
                        address = ""
                    
                    if name:
                        restaurants.append((name, address))
                    
                except Exception as item_error:
                    self.logger.error(f"아이템 {idx} 추출 중 오류: {item_error}")
                    continue
            
        except TimeoutError:
            self.logger.error("리스트를 찾을 수 없습니다.")
        except Exception as e:
            self.logger.error(f"음식점 목록 추출 중 오류: {e}")
        
        return restaurants
    
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
            crawling_manager = CrawlingManager("Bluer")
            
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
    
    async def _crawl_single_store_parallel(self, page: Page, store: tuple):
        """
        단일 매장 크롤링 (병렬용)
        
        Returns:
            Tuple: (store_data, name) 또는 None
        """
        name, address = store
        
        try:
            # 검색 전략 사용
            async def extract_callback(entry_frame, page):
                extractor = StoreDetailExtractor(entry_frame, page)
                return await extractor.extract_all_details()
            
            store_data = await self.search_strategy.search_with_multiple_strategies(
                page=page,
                store_name=name,
                road_address=address,
                extractor_callback=extract_callback
            )
            
            if store_data:
                # 리소스 정리
                await OptimizedBrowserManager.clear_page_resources(page)
                return (store_data, name)
            
            return None
            
        except Exception as e:
            self.logger.error(f"'{name}' 크롤링 중 오류: {e}")
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
                log_prefix="Bluer"
            )
        
        return wrapper


async def main():
    """메인 함수"""
    logger = get_logger(__name__)
    
    logger.info("Bluer 음식점 크롤러 시작 (병렬 처리)")
    
    try:
        crawler = BluerRestaurantCrawler(headless=False)
        
        await crawler.crawl_all_pages(
            delay=5,
            naver_delay=15
        )
        
        logger.info("크롤러 종료")
        
    except Exception as e:
        logger.error(f"크롤링 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())