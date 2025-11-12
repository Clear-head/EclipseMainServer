"""
DiningCode 웹사이트 음식점 크롤링 모듈 (메모리 최적화 + 봇 우회 + 병렬 처리)
1단계: DiningCode에서 전체 목록 수집 → 2단계: 네이버 지도에서 배치 병렬 크롤링
"""
import asyncio
import re

from playwright.async_api import async_playwright, TimeoutError, Page

from src.logger.custom_logger import get_logger
from src.service.crawl.utils.crawling_manager import CrawlingManager
from src.service.crawl.utils.human_like_actions import HumanLikeActions
# 공통 모듈 import
from src.service.crawl.utils.optimized_browser_manager import OptimizedBrowserManager
from src.service.crawl.utils.search_strategy import NaverMapSearchStrategy
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor


class DiningCodeRestaurantCrawler:
    """DiningCode 웹사이트 음식점 크롤링 클래스 (병렬 처리)"""
    
    RESTART_INTERVAL = 50  # 50개마다 컨텍스트 재시작
    
    def __init__(self, headless: bool = False):
        self.logger = get_logger(__name__)
        self.headless = headless
        self.diningcode_url = "https://www.diningcode.com/list.dc?query=%EC%84%9C%EC%9A%B8%20%EC%B9%B4%ED%8E%98"
        self.data_saver = StoreDataSaver()
        self.search_strategy = NaverMapSearchStrategy()
        self.human_actions = HumanLikeActions()
        self.success_count = 0
        self.fail_count = 0
    
    async def crawl_all_pages(self, delay: int = 5, naver_delay: int = 20):
        """
        DiningCode 전체 페이지 병렬 크롤링
        1단계: DiningCode에서 전체 목록 수집 → 2단계: 네이버 지도에서 배치 병렬 크롤링
        
        Args:
            delay: DiningCode 페이지 간 딜레이 (초)
            naver_delay: 네이버 지도 크롤링 딜레이 (초)
        """
        async with async_playwright() as p:
            # 1단계: DiningCode에서 전체 음식점 목록 수집
            self.logger.info("1단계: DiningCode 전체 목록 수집 시작")
            
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
                    self.logger.info(f"성공률: {self.success_count/total*100:.1f}%")
                
            finally:
                await naver_browser.close()
    
    async def _collect_all_restaurants(self, playwright, delay: int) -> list:
        """DiningCode에서 전체 음식점 목록만 수집"""
        # 🔥 봇 탐지 회피를 위한 최적화된 브라우저 사용
        browser = await OptimizedBrowserManager.create_optimized_browser(playwright, self.headless)
        context = await OptimizedBrowserManager.create_stealth_context(browser)
        page = await context.new_page()
        
        all_restaurants = []
        
        try:
            self.logger.info(f"DiningCode 페이지 접속 중...")
            
            # 🔥 타임아웃 증가 + domcontentloaded로 변경 (더 빠른 로딩)
            try:
                await page.goto(
                    self.diningcode_url, 
                    wait_until='domcontentloaded',  # networkidle 대신 domcontentloaded
                    timeout=60000  # 60초로 증가
                )
                self.logger.info("페이지 로딩 완료")
            except TimeoutError:
                self.logger.warning("페이지 로딩 타임아웃, 현재 상태로 진행 시도...")
            
            # 페이지가 로드될 때까지 추가 대기
            await asyncio.sleep(5)
            
            # 🔥 페이지 스크롤 (컨텐츠 로드 유도)
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
            await asyncio.sleep(2)
            await page.evaluate('window.scrollTo(0, 0)')
            await asyncio.sleep(2)
            
            # "맛집 더보기" 버튼을 사라질 때까지 클릭
            await self._click_load_more_button(page)
            
            # 음식점 목록 수집
            self.logger.info("음식점 목록 추출 중...")
            restaurants = await self._extract_restaurants_from_page(page)
            
            if restaurants:
                self.logger.info(f"총 {len(restaurants)}개 음식점 수집")
                all_restaurants.extend(restaurants)
            else:
                self.logger.warning("음식점을 찾지 못했습니다.")
            
        except Exception as e:
            self.logger.error(f"DiningCode 목록 수집 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            await context.close()
            await browser.close()
        
        return all_restaurants
    
    async def _click_load_more_button(self, page: Page):
        """
        "맛집 더보기" 버튼을 사라질 때까지 반복 클릭
        
        Args:
            page: Playwright Page 객체
        """
        click_count = 0
        max_attempts = 100  # 무한 루프 방지
        
        self.logger.info("'맛집 더보기' 버튼 클릭 시작...")
        
        while click_count < max_attempts:
            try:
                # 더보기 버튼 선택자 (여러 선택자 시도)
                selectors = [
                    'div.SearchMore.upper[aria-label="search more in here"]',
                    'div[aria-label="search more in here"]'
                ]
                
                button_found = False
                load_more_button = None
                
                # 여러 선택자 시도
                for selector in selectors:
                    try:
                        load_more_button = page.locator(selector)
                        if await load_more_button.count() > 0:
                            button_found = True
                            self.logger.debug(f"버튼 발견: {selector}")
                            break
                    except:
                        continue
                
                if not button_found or load_more_button is None:
                    self.logger.info(f"'맛집 더보기' 버튼을 더 이상 찾을 수 없습니다. (총 {click_count}회 클릭)")
                    break
                
                # 버튼이 보이는지 확인 (타임아웃 10초)
                if await load_more_button.is_visible(timeout=10000):
                    # 버튼으로 스크롤
                    await load_more_button.scroll_into_view_if_needed()
                    await asyncio.sleep(1)
                    
                    # 🔥 여러 방법으로 클릭 시도
                    try:
                        # 1. 일반 클릭
                        await load_more_button.click(timeout=5000)
                    except:
                        try:
                            # 2. force 클릭
                            await load_more_button.click(force=True, timeout=5000)
                        except:
                            # 3. JavaScript 클릭
                            await page.evaluate('''
                                () => {
                                    const button = document.querySelector('div.SearchMore.upper');
                                    if (button) button.click();
                                }
                            ''')
                    
                    click_count += 1
                    self.logger.info(f"'맛집 더보기' 버튼 클릭 ({click_count}회)")
                    
                    # 로딩 대기 (점진적 증가)
                    wait_time = min(3 + (click_count * 0.1), 5)  # 최대 5초
                    await asyncio.sleep(wait_time)
                else:
                    # 버튼이 더 이상 보이지 않으면 종료
                    self.logger.info(f"'맛집 더보기' 버튼이 사라졌습니다. (총 {click_count}회 클릭)")
                    break
                    
            except TimeoutError:
                # 타임아웃 = 버튼이 더 이상 없음
                self.logger.info(f"'맛집 더보기' 버튼을 찾을 수 없습니다. (총 {click_count}회 클릭)")
                break
            except Exception as e:
                self.logger.warning(f"버튼 클릭 중 오류 (무시하고 계속): {e}")
                break
        
        if click_count >= max_attempts:
            self.logger.warning(f"최대 클릭 횟수({max_attempts})에 도달했습니다.")
    
    async def _extract_restaurants_from_page(self, page: Page) -> list:
        """
        현재 페이지에서 음식점 이름 추출 (숫자. 제거)
        
        Args:
            page: Playwright Page 객체
            
        Returns:
            list: [(음식점명, ""), ...] 형태의 리스트 (주소는 비어있음)
        """
        restaurants = []
        
        try:
            # 🔥 여러 선택자 시도
            selectors = [
                '[id^="title"]',  # ID가 title로 시작
                'div[id^="title"]',
                'span[id^="title"]',
                'a[id^="title"]'
            ]
            
            title_elements = []
            
            for selector in selectors:
                try:
                    elements = await page.locator(selector).all()
                    if elements:
                        title_elements = elements
                        self.logger.info(f"총 {len(title_elements)}개 title 요소 발견 (선택자: {selector})")
                        break
                except:
                    continue
            
            if not title_elements:
                self.logger.error("음식점 이름 요소를 찾을 수 없습니다.")
                
                # 🔥 디버깅: 페이지 HTML 일부 출력
                try:
                    html_sample = await page.content()
                    self.logger.debug(f"페이지 HTML 샘플 (첫 1000자): {html_sample[:1000]}")
                except:
                    pass
                
                return []
            
            for idx, element in enumerate(title_elements, 1):
                try:
                    # 텍스트 추출
                    text = await element.inner_text(timeout=3000)
                    
                    if text and text.strip():
                        # 숫자와 점(.) 제거 (예: "1. 스타벅스" → "스타벅스")
                        # 정규식: 숫자 + 점 + 공백 제거
                        cleaned_name = re.sub(r'^\d+\.\s*', '', text.strip())
                        
                        if cleaned_name:
                            restaurants.append((cleaned_name, ""))  # 주소는 빈 문자열
                            
                            # 로깅 (10개마다)
                            if idx % 10 == 0:
                                self.logger.debug(f"추출 중... {idx}개")
                    
                except Exception as item_error:
                    self.logger.error(f"아이템 {idx} 추출 중 오류: {item_error}")
                    continue
            
            self.logger.info(f"음식점 이름 추출 완료: {len(restaurants)}개")
            
        except TimeoutError:
            self.logger.error("음식점 목록을 찾을 수 없습니다.")
        except Exception as e:
            self.logger.error(f"음식점 목록 추출 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        
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
            # 병렬 처리: CrawlingManager 사용
            crawling_manager = CrawlingManager("DiningCode")
            
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
        
        Args:
            page: Playwright Page 객체
            store: (name, "") 튜플
            
        Returns:
            Tuple: (store_data, name) 또는 None
        """
        name, _ = store  # 주소는 비어있음
        
        try:
            # 검색 전략 사용 (이름만으로 검색)
            async def extract_callback(entry_frame, page):
                extractor = StoreDetailExtractor(entry_frame, page)
                return await extractor.extract_all_details()
            
            # 주소 없이 이름만으로 검색
            store_data = await self.search_strategy.search_with_multiple_strategies(
                page=page,
                store_name=name,
                road_address="",  # 주소 없음
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
        async def wrapper(idx: int, total_stores: int, store_data_tuple, store_name: str):
            if store_data_tuple is None:
                return (False, "크롤링 실패")
            
            store_data, actual_name = store_data_tuple
            global_idx = batch_start + idx
            
            return await self.data_saver.save_store_data(
                idx=global_idx,
                total=total,
                store_data=store_data,
                store_name=actual_name,
                log_prefix="DiningCode"
            )
        
        return wrapper


async def main():
    """메인 함수"""
    logger = get_logger(__name__)
    
    logger.info("DiningCode 음식점 크롤러 시작 (병렬 처리)")
    
    try:
        crawler = DiningCodeRestaurantCrawler(headless=True)
        
        await crawler.crawl_all_pages(
            delay=5,
            naver_delay=15
        )
        
        logger.info("크롤러 종료")
        
    except Exception as e:
        logger.error(f"크롤링 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())