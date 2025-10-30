"""
네이버 지도 즐겨찾기 목록 크롤링 모듈 (메모리 최적화 + 봇 우회 + 병렬 처리)
배치 단위로 컨텍스트를 재생성하여 메모리 누수 방지
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
from src.service.crawl.utils.scroll_helper import FavoriteListScroller
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.crawling_manager import CrawlingManager


class NaverMapFavoriteCrawler:
    """네이버 지도 즐겨찾기 목록 크롤링 클래스 (메모리 최적화 + 병렬 처리)"""
    
    RESTART_INTERVAL = 30  # 30개마다 컨텍스트 재시작
    
    def __init__(self, headless: bool = False):
        self.logger = get_logger(__name__)
        self.headless = headless
        self.data_saver = StoreDataSaver()
        self.human_actions = HumanLikeActions()
        self.success_count = 0
        self.fail_count = 0
    
    async def crawl_favorite_list(self, favorite_url: str, delay: int = 20):
        """
        네이버 지도 즐겨찾기 목록에서 장소들을 병렬 크롤링
        배치 단위로 컨텍스트를 재생성하여 메모리 누수 방지
        
        Args:
            favorite_url: 즐겨찾기 URL
            delay: 각 장소 크롤링 사이의 기본 대기 시간(초)
        """
        async with async_playwright() as p:
            browser = await OptimizedBrowserManager.create_optimized_browser(p, self.headless)
            
            try:
                # 1단계: 전체 장소 개수 파악
                total = await self._get_total_place_count(browser, favorite_url)
                
                if total == 0:
                    self.logger.warning("크롤링할 장소가 없습니다.")
                    return
                
                self.logger.info(f"총 {total}개 장소 크롤링 시작 (병렬 처리)")
                self.logger.info(f"배치 크기: {self.RESTART_INTERVAL}개")
                self.logger.info(f"예상 배치 수: {(total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL}개")
                
                # 2단계: 배치 단위로 병렬 크롤링
                for batch_start in range(0, total, self.RESTART_INTERVAL):
                    batch_end = min(batch_start + self.RESTART_INTERVAL, total)
                    batch_num = batch_start // self.RESTART_INTERVAL + 1
                    total_batches = (total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL
                    
                    self.logger.info(f"배치 {batch_num}/{total_batches}: {batch_start+1}~{batch_end}/{total} 처리 시작")
                    
                    # 새 컨텍스트 생성
                    context = await OptimizedBrowserManager.create_stealth_context(browser)
                    page = await context.new_page()
                    
                    try:
                        # 배치 병렬 크롤링 실행
                        await self._process_batch_parallel(
                            page, favorite_url, 
                            batch_start, batch_end, total, delay
                        )
                        
                    except Exception as e:
                        self.logger.error(f"배치 {batch_start+1}~{batch_end} 처리 중 오류: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())
                    finally:
                        await context.close()
                        await asyncio.sleep(3)
                        
                        # 배치 간 긴 휴식
                        if batch_end < total:
                            import random
                            rest_time = random.uniform(20, 40)
                            self.logger.info(f"배치 {batch_num} 완료! {rest_time:.0f}초 휴식 후 다음 배치 시작...\n")
                            await asyncio.sleep(rest_time)
                
                # 3단계: 최종 결과 출력
                self.logger.info(f"전체 크롤링 완료!")
                self.logger.info(f"총 처리: {total}개")
                self.logger.info(f"성공: {self.success_count}개")
                self.logger.info(f"실패: {self.fail_count}개")
                if total > 0:
                    self.logger.info(f"성공률: {self.success_count/total*100:.1f}%")
                
            except Exception as e:
                self.logger.error(f"크롤링 중 치명적 오류: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                await browser.close()
    
    async def _get_total_place_count(self, browser, favorite_url: str) -> int:
        """전체 장소 개수만 빠르게 파악"""
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            self.logger.info("전체 장소 개수 확인 중...")
            
            await page.goto(favorite_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(10)
            
            list_frame_locator = page.frame_locator('iframe#myPlaceBookmarkListIframe')
            list_frame = page.frame('myPlaceBookmarkListIframe')
            
            if not list_frame:
                self.logger.error("myPlaceBookmarkListIframe을 찾을 수 없습니다.")
                return 0
            
            await asyncio.sleep(3)
            
            place_selector = await self._find_place_selector(list_frame_locator, list_frame)
            if not place_selector:
                return 0
            
            # 스크롤하여 전체 로드
            count = await FavoriteListScroller.scroll_to_load_all(
                frame_locator=list_frame_locator,
                item_selector=place_selector
            )
            
            self.logger.info(f"총 {count}개 장소 확인 완료\n")
            
            return count
            
        except Exception as e:
            self.logger.error(f"전체 개수 확인 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0
        finally:
            await context.close()
    
    async def _process_batch_parallel(
        self, 
        page: Page, 
        favorite_url: str,
        batch_start: int, 
        batch_end: int, 
        total: int, 
        delay: int
    ):
        """
        배치 단위 병렬 크롤링
        
        Args:
            page: Playwright Page 객체
            favorite_url: 즐겨찾기 URL
            batch_start: 배치 시작 인덱스
            batch_end: 배치 종료 인덱스
            total: 전체 장소 수
            delay: 기본 대기 시간
        """
        try:
            # 페이지 로드 및 iframe 설정
            self.logger.debug("즐겨찾기 페이지 로드 중...")
            await page.goto(favorite_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(10)
            
            await page.wait_for_selector('iframe#myPlaceBookmarkListIframe', timeout=30000)
            list_frame_locator = page.frame_locator('iframe#myPlaceBookmarkListIframe')
            list_frame = page.frame('myPlaceBookmarkListIframe')
            
            if not list_frame:
                self.logger.error("myPlaceBookmarkListIframe을 찾을 수 없습니다.")
                return
            
            await asyncio.sleep(3)
            
            place_selector = await self._find_place_selector(list_frame_locator, list_frame)
            if not place_selector:
                self.logger.error("장소 선택자를 찾을 수 없습니다.")
                return
            
            # batch_end까지 스크롤
            await FavoriteListScroller.scroll_to_index(
                frame_locator=list_frame_locator,
                item_selector=place_selector,
                target_index=batch_end
            )
            
            # ========================================
            # 🔥 병렬 처리: CrawlingManager 사용
            # ========================================
            batch_items = list(range(batch_start, batch_end))
            
            crawling_manager = CrawlingManager("즐겨찾기")
            
            await crawling_manager.execute_crawling_with_save(
                stores=batch_items,
                crawl_func=lambda idx, i, t: self._crawl_single_place_parallel(
                    page, list_frame_locator, place_selector, idx, total
                ),
                save_func=self._save_wrapper,
                delay=delay
            )
            
            # 성공/실패 카운트 업데이트
            self.success_count += crawling_manager.success_count
            self.fail_count += crawling_manager.fail_count
            
            batch_num = batch_start // self.RESTART_INTERVAL + 1
            self.logger.info(f"배치 {batch_num} ({batch_start+1}~{batch_end}) 완료!")
            
        except Exception as e:
            self.logger.error(f"배치 처리 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def _crawl_single_place_parallel(
        self,
        page: Page,
        list_frame_locator,
        place_selector: str,
        idx: int,
        total: int
    ):
        """
        단일 장소 크롤링 (병렬용)
        
        Returns:
            Tuple: (store_data, place_name) 또는 None
        """
        try:
            # 매번 목록 새로 가져오기
            places = await list_frame_locator.locator(place_selector).all()
            
            if idx >= len(places):
                self.logger.error(f"인덱스 범위 초과: {idx}/{len(places)}")
                return None
            
            place = places[idx]
            place_name = await self._extract_place_name(place, idx)
            
            # 사람처럼 클릭
            await self.human_actions.human_like_click(place)
            await asyncio.sleep(3)
            
            # 폐업 팝업 체크
            if await self._check_and_close_popup(list_frame_locator, place_name):
                self.logger.warning(f"'{place_name}' 폐업 또는 접근 불가")
                return None
            
            # entry iframe
            entry_frame = await self._get_entry_frame(page)
            if not entry_frame:
                self.logger.error(f"'{place_name}' entry iframe 없음")
                return None
            
            # 상세 정보 추출
            extractor = StoreDetailExtractor(entry_frame, page)
            store_data = await extractor.extract_all_details()
            
            if store_data:
                # 리소스 정리
                await OptimizedBrowserManager.clear_page_resources(page)
                return (store_data, place_name)
            else:
                self.logger.error(f"'{place_name}' 정보 추출 실패")
                return None
                
        except Exception as e:
            self.logger.error(f"크롤링 중 오류: {e}")
            return None
    
    async def _save_wrapper(self, idx: int, total: int, store_data_tuple, place_name: str):
        """
        저장 래퍼 (CrawlingManager용)
        
        Args:
            store_data_tuple: (store_data, place_name) 튜플 또는 None
        """
        if store_data_tuple is None:
            return (False, "크롤링 실패")
        
        store_data, actual_name = store_data_tuple
        
        return await self.data_saver.save_store_data(
            idx=idx,
            total=total,
            store_data=store_data,
            store_name=actual_name,
            log_prefix="즐겨찾기"
        )
    
    async def _find_place_selector(self, list_frame_locator, list_frame):
        """장소 선택자 찾기"""
        possible_selectors = [
            '#app > div > div:nth-child(3) > div > ul > li',
            'ul.list_place > li',
            'ul > li',
            '[role="list"] > *',
        ]
        
        for selector in possible_selectors:
            try:
                elements = await list_frame_locator.locator(selector).all()
                if len(elements) > 0:
                    self.logger.debug(f"선택자 발견: {selector}")
                    return selector
            except:
                continue
        
        self.logger.error("장소 목록 선택자를 찾을 수 없습니다.")
        return None
    
    async def _extract_place_name(self, place, idx: int) -> str:
        """장소명 추출"""
        try:
            name_selectors = ['div.name', 'span.name', '.place_name', 'a.name', '.item_name', 'span']
            
            for name_sel in name_selectors:
                try:
                    place_name = await place.locator(name_sel).first.inner_text(timeout=2000)
                    if place_name and place_name.strip():
                        return place_name.strip()
                except:
                    continue
            
            return f"장소 {idx+1}"
        except:
            return f"장소 {idx+1}"
    
    async def _check_and_close_popup(self, list_frame_locator, place_name: str) -> bool:
        """폐업 팝업 체크 및 닫기"""
        popup_selectors = [
            'body > div:nth-child(4) > div._show_62e0u_8',
            'div._show_62e0u_8',
            'div._popup_62e0u_1._show_62e0u_8',
            'div[class*="_show_"]',
            'div._popup_62e0u_1',
        ]
        
        is_popup_found = False
        
        for popup_selector in popup_selectors:
            try:
                popup_element = list_frame_locator.locator(popup_selector).first
                is_visible = await popup_element.is_visible(timeout=1000)
                
                if is_visible:
                    is_popup_found = True
                    break
            except:
                continue
        
        if is_popup_found:
            button_selectors = [
                'body > div:nth-child(4) > div > div._popup_62e0u_1._at_pc_62e0u_21._show_62e0u_8 > div._popup_buttons_62e0u_85 > button',
                'div._popup_buttons_62e0u_85 > button',
            ]
            
            for button_selector in button_selectors:
                try:
                    popup_button = list_frame_locator.locator(button_selector).first
                    if await popup_button.is_visible(timeout=1000):
                        await popup_button.click(timeout=2000)
                        await asyncio.sleep(0.5)
                        break
                except:
                    continue
        
        return is_popup_found
    
    async def _get_entry_frame(self, page: Page):
        """상세 정보 iframe 가져오기"""
        try:
            await page.wait_for_selector('iframe#entryIframe', timeout=10000)
            entry_frame = page.frame_locator('iframe#entryIframe')
            await asyncio.sleep(3)
            return entry_frame
        except TimeoutError:
            return None


async def main(favorite_url='https://map.naver.com/p/favorite/YOUR_URL'):
    """메인 함수"""
    logger = get_logger(__name__)
    

    logger.info("네이버 지도 즐겨찾기 크롤러 시작 (병렬 처리)")

    
    crawler = NaverMapFavoriteCrawler(headless=False)
    
    await crawler.crawl_favorite_list(
        favorite_url=favorite_url,
        delay=15
    )
    

    logger.info("크롤러 종료")