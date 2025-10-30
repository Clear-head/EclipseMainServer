"""
네이버 지도 콘텐츠(놀거리) 검색 크롤링 모듈 (메모리 최적화 + 봇 우회 + 병렬 처리)
목록 클릭 방식
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
from src.service.crawl.utils.scroll_helper import SearchResultScroller, PageNavigator
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.crawling_manager import CrawlingManager


class NaverMapContentCrawler:
    """네이버 지도 콘텐츠(놀거리) 검색 크롤링 클래스 (목록 클릭 방식)"""
    
    CONTENT_KEYWORDS = [
        "서울 미술관",
        "서울 동물카페",
        "서울 공방",
        "서울 사격장",
        "서울 근교유적지",
        "서울 박물관",
        "서울 클라이밍",
    ]
    
    RESTART_INTERVAL = 30  # 30개마다 컨텍스트 재시작
    
    def __init__(self, headless: bool = False):
        self.logger = get_logger(__name__)
        self.headless = headless
        self.naver_map_url = "https://map.naver.com/v5/search"
        self.data_saver = StoreDataSaver()
        self.human_actions = HumanLikeActions()
        self.success_count = 0
        self.fail_count = 0
    
    async def crawl_by_keywords(self, keywords: list = None, delay: int = 20):
        """키워드 목록으로 병렬 크롤링 (목록 클릭 방식)"""
        keywords = keywords or self.CONTENT_KEYWORDS
        
        async with async_playwright() as p:
            browser = await OptimizedBrowserManager.create_optimized_browser(p, self.headless)
            
            try:
                self.logger.info(f"\n{'='*70}")
                self.logger.info(f"📊 총 {len(keywords)}개 키워드 크롤링 시작 (병렬 처리 + 목록 클릭)")
                self.logger.info(f"{'='*70}\n")
                
                for keyword_idx, keyword in enumerate(keywords, 1):
                    self.logger.info(f"\n{'='*70}")
                    self.logger.info(f"[키워드 {keyword_idx}/{len(keywords)}] '{keyword}' 크롤링 시작")
                    self.logger.info(f"{'='*70}\n")
                    
                    # 키워드별로 페이지 단위 처리
                    await self._crawl_keyword_by_pages(browser, keyword, delay)
                    
                    self.logger.info(f"✅ [키워드 {keyword_idx}/{len(keywords)}] '{keyword}' 완료\n")
                    
                    if keyword_idx < len(keywords):
                        import random
                        rest_time = random.uniform(40, 60)
                        self.logger.info(f"🛌 키워드 완료, {rest_time:.0f}초 휴식...\n")
                        await asyncio.sleep(rest_time)
                
                self.logger.info(f"\n{'='*70}")
                self.logger.info(f"✅ 모든 키워드 크롤링 완료!")
                self.logger.info(f"   성공: {self.success_count}개")
                self.logger.info(f"   실패: {self.fail_count}개")
                self.logger.info(f"{'='*70}\n")
                
            except Exception as e:
                self.logger.error(f"크롤링 중 오류: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                await browser.close()
    
    async def _crawl_keyword_by_pages(self, browser, keyword: str, delay: int):
        """
        키워드별로 페이지 단위로 크롤링
        각 페이지마다 배치 처리
        """
        # 1단계: 전체 페이지 수 및 아이템 개수 파악
        total_items, total_pages = await self._get_total_items_count(browser, keyword)
        
        if total_items == 0:
            self.logger.warning(f"'{keyword}' 결과 없음")
            return
        
        self.logger.info(f"✅ '{keyword}' 총 {total_items}개 ({total_pages}페이지)")
        
        # 2단계: 배치 단위로 페이지 크롤링
        items_processed = 0
        
        for batch_start in range(0, total_items, self.RESTART_INTERVAL):
            batch_end = min(batch_start + self.RESTART_INTERVAL, total_items)
            
            batch_num = batch_start // self.RESTART_INTERVAL + 1
            total_batches = (total_items + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL
            
            self.logger.info(f"\n🔄 [{keyword}] 배치 {batch_num}/{total_batches}: {batch_start+1}~{batch_end}/{total_items}")
            
            # 새 컨텍스트 생성
            context = await OptimizedBrowserManager.create_stealth_context(browser)
            page = await context.new_page()
            
            try:
                # 배치 처리 (목록 클릭 방식)
                items_processed = await self._process_batch_with_click(
                    page, keyword, batch_start, batch_end, total_items, delay
                )
                
            except Exception as e:
                self.logger.error(f"배치 처리 중 오류: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                await context.close()
                await asyncio.sleep(3)
                
                if batch_end < total_items:
                    import random
                    rest_time = random.uniform(20, 40)
                    self.logger.info(f"🛌 배치 완료, {rest_time:.0f}초 휴식...\n")
                    await asyncio.sleep(rest_time)
    
    async def _get_total_items_count(self, browser, keyword: str) -> tuple:
        """
        전체 아이템 개수 및 페이지 수 파악
        
        Returns:
            Tuple[int, int]: (전체 아이템 수, 전체 페이지 수)
        """
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            self.logger.info(f"  '{keyword}' 전체 개수 확인 중...")
            
            await page.goto(self.naver_map_url, wait_until='domcontentloaded')
            await asyncio.sleep(3)
            
            # 검색
            search_input_selector = '.input_search'
            await page.wait_for_selector(search_input_selector)
            await page.fill(search_input_selector, '')
            await asyncio.sleep(0.5)
            
            await page.fill(search_input_selector, keyword)
            await page.press(search_input_selector, 'Enter')
            await asyncio.sleep(5)
            
            # searchIframe 대기
            await page.wait_for_selector('iframe#searchIframe', timeout=10000)
            search_frame_locator = page.frame_locator('iframe#searchIframe')
            search_frame = page.frame('searchIframe')
            
            if not search_frame:
                return 0, 0
            
            await asyncio.sleep(3)
            
            # 페이지별로 스크롤하여 전체 개수 파악
            total_items = 0
            page_num = 1
            
            while True:
                # 현재 페이지 스크롤
                item_count = await SearchResultScroller.scroll_current_page(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                if item_count == 0:
                    break
                
                total_items += item_count
                
                # 다음 페이지 확인
                has_next = await PageNavigator.go_to_next_page_naver(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                if not has_next:
                    break
                
                page_num += 1
                await asyncio.sleep(2)
            
            return total_items, page_num
            
        except Exception as e:
            self.logger.error(f"'{keyword}' 전체 개수 확인 중 오류: {e}")
            return 0, 0
        finally:
            await context.close()
    
    async def _process_batch_with_click(
        self,
        page: Page,
        keyword: str,
        batch_start: int,
        batch_end: int,
        total: int,
        delay: int
    ):
        """
        배치 단위 병렬 크롤링 (목록 클릭 방식)
        """
        try:
            # 네이버 지도 검색
            await page.goto(self.naver_map_url, wait_until='domcontentloaded')
            await asyncio.sleep(3)
            
            search_input_selector = '.input_search'
            await page.wait_for_selector(search_input_selector)
            await page.fill(search_input_selector, '')
            await asyncio.sleep(0.5)
            
            await page.fill(search_input_selector, keyword)
            await page.press(search_input_selector, 'Enter')
            await asyncio.sleep(5)
            
            # searchIframe 대기
            await page.wait_for_selector('iframe#searchIframe', timeout=10000)
            search_frame_locator = page.frame_locator('iframe#searchIframe')
            search_frame = page.frame('searchIframe')
            
            if not search_frame:
                self.logger.error("searchIframe을 찾을 수 없습니다.")
                return 0
            
            await asyncio.sleep(3)
            
            # batch_start 위치까지 페이지 이동 및 스크롤
            current_idx = 0
            current_page = 1
            
            while current_idx < batch_end:
                # 현재 페이지 스크롤
                await SearchResultScroller.scroll_current_page(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                # 현재 페이지의 아이템 개수
                item_selector = '#_pcmap_list_scroll_container > ul > li'
                items = await search_frame_locator.locator(item_selector).all()
                items_in_page = len(items)
                
                # 이 페이지에서 크롤링할 아이템 범위 계산
                page_start = max(0, batch_start - current_idx)
                page_end = min(items_in_page, batch_end - current_idx)
                
                # 크롤링할 아이템이 이 페이지에 있으면
                if page_start < items_in_page and current_idx < batch_end:
                    # 이 페이지의 아이템 리스트 생성
                    batch_items = []
                    
                    # ========================================
                    # 🔥 수정: 아이템명 미리 추출
                    # ========================================
                    for idx in range(page_start, page_end):
                        if current_idx + idx >= batch_start and current_idx + idx < batch_end:
                            try:
                                # 아이템 요소 가져오기
                                item = items[idx]
                                
                                # 아이템 이름 추출
                                item_name = await self._extract_item_name(item, idx, items_in_page)
                                
                                batch_items.append({
                                    'page_idx': idx,
                                    'global_idx': current_idx + idx,
                                    'page_num': current_page,
                                    'name': item_name  # ✅ 이름 추가!
                                })
                            except Exception as e:
                                self.logger.warning(f"아이템 {idx} 이름 추출 실패: {e}")
                                # 실패해도 계속 진행 (이름 없이)
                                batch_items.append({
                                    'page_idx': idx,
                                    'global_idx': current_idx + idx,
                                    'page_num': current_page,
                                    'name': f"아이템 {current_idx + idx + 1}"
                                })
                    
                    if batch_items:
                        # ========================================
                        # 🔥 병렬 처리: CrawlingManager 사용
                        # ========================================
                        crawling_manager = CrawlingManager("콘텐츠")
                        
                        await crawling_manager.execute_crawling_with_save(
                            stores=batch_items,
                            crawl_func=lambda item, i, t: self._crawl_single_item_from_list(
                                page, search_frame_locator, item_selector, item, total
                            ),
                            save_func=self._save_wrapper_with_total(total),
                            delay=delay
                        )
                        
                        # 성공/실패 카운트 업데이트
                        self.success_count += crawling_manager.success_count
                        self.fail_count += crawling_manager.fail_count
                
                # 현재 인덱스 업데이트
                current_idx += items_in_page
                
                # 다음 페이지로 이동 (필요한 경우)
                if current_idx < batch_end:
                    has_next = await PageNavigator.go_to_next_page_naver(
                        search_frame_locator=search_frame_locator,
                        search_frame=search_frame
                    )
                    
                    if not has_next:
                        self.logger.warning(f"다음 페이지 없음 (현재: {current_idx}/{batch_end})")
                        break
                    
                    current_page += 1
                    await asyncio.sleep(3)
                else:
                    break
            
            return current_idx
            
        except Exception as e:
            self.logger.error(f"배치 처리 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0
    
    async def _crawl_single_item_from_list(
        self,
        page: Page,
        search_frame_locator,
        item_selector: str,
        item_info: dict,
        total: int
    ):
        """
        목록에서 단일 아이템 클릭하여 크롤링 (병렬용)
        
        Args:
            page: 메인 페이지
            search_frame_locator: 검색 iframe locator
            item_selector: 아이템 선택자
            item_info: 아이템 정보 (page_idx, global_idx 포함)
            total: 전체 개수
            
        Returns:
            Tuple: (store_data, name) 또는 None
        """
        page_idx = item_info['page_idx']
        global_idx = item_info['global_idx']
        
        try:
            # 매번 목록 새로 가져오기 (DOM 변경 대응)
            items = await search_frame_locator.locator(item_selector).all()
            
            if page_idx >= len(items):
                self.logger.error(f"[{global_idx+1}/{total}] 인덱스 범위 초과: {page_idx}/{len(items)}")
                return None
            
            item = items[page_idx]
            
            # 아이템 이름 추출
            name = await self._extract_item_name(item, page_idx, len(items))
            
            # 클릭 요소 찾기
            click_element = await self._find_click_element(item, page_idx)
            
            if not click_element:
                self.logger.error(f"[{global_idx+1}/{total}] '{name}' 클릭 요소 없음")
                return None
            
            # 사람처럼 클릭
            await self.human_actions.human_like_click(click_element)
            await asyncio.sleep(3)
            
            # entryIframe 대기
            try:
                await page.wait_for_selector('iframe#entryIframe', timeout=10000)
                entry_frame = page.frame_locator('iframe#entryIframe')
                await asyncio.sleep(3)
                
                # 상세 정보 추출
                extractor = StoreDetailExtractor(entry_frame, page)
                store_data = await extractor.extract_all_details()
                
                if store_data:
                    actual_name = store_data[0]
                    
                    # 리소스 정리
                    await OptimizedBrowserManager.clear_page_resources(page)
                    
                    return (store_data, actual_name)
                else:
                    self.logger.error(f"[{global_idx+1}/{total}] '{name}' 정보 추출 실패")
                    return None
                    
            except TimeoutError:
                self.logger.error(f"[{global_idx+1}/{total}] '{name}' entryIframe 타임아웃")
                return None
                
        except Exception as e:
            self.logger.error(f"[{global_idx+1}/{total}] 크롤링 중 오류: {e}")
            return None
    
    def _save_wrapper_with_total(self, total: int):
        """저장 래퍼 팩토리"""
        async def wrapper(idx: int, _, store_data_tuple, store_name: str):
            if store_data_tuple is None:
                return (False, "크롤링 실패")
            
            store_data, actual_name = store_data_tuple
            
            return await self.data_saver.save_store_data(
                idx=idx,
                total=total,
                store_data=store_data,
                store_name=actual_name,
                log_prefix="콘텐츠"
            )
        
        return wrapper
    
    async def _extract_item_name(self, item, idx: int, item_count: int) -> str:
        """아이템 이름 추출 (4가지 선택자 시도)"""
        name_selectors = [
            'div.Dr2xO > div.pIwpC > a > span.CMy2_',
            'div.qbGlu > div.ouxiq > div.ApCpt > a > span.YwYLL',
            'div.Np1CD > div:nth-child(2) > div.SbNoJ > a > span.t3s7S',
            'div.Np1CD > div > div.SbNoJ > a > span.t3s7S',
        ]
        
        for selector in name_selectors:
            try:
                name_element = item.locator(selector).first
                if await name_element.count() > 0:
                    name = await name_element.inner_text(timeout=2000)
                    if name and name.strip():
                        return name.strip()
            except:
                continue
        
        return f"아이템 {idx+1}"
    
    async def _find_click_element(self, item, idx: int):
        """클릭 요소 찾기 (4가지 선택자 시도)"""
        link_selectors = [
            'div.Dr2xO > div.pIwpC > a',
            'div.qbGlu > div.ouxiq > div.ApCpt > a',
            'div.Np1CD > div:nth-child(2) > div.SbNoJ > a',
            'div.Np1CD > div > div.SbNoJ > a',
        ]
        
        for selector in link_selectors:
            try:
                element = item.locator(selector).first
                if await element.count() > 0:
                    return element
            except:
                continue
        
        # 모두 실패하면 아이템 전체 반환
        return item


async def main():
    """메인 함수"""
    logger = get_logger(__name__)
    
    logger.info("="*70)
    logger.info("🚀 네이버 지도 콘텐츠 크롤러 시작 (병렬 처리 + 목록 클릭)")
    logger.info("="*70)
    
    try:
        crawler = NaverMapContentCrawler(headless=False)
        
        await crawler.crawl_by_keywords(
            keywords=None,
            delay=15
        )
        
        logger.info("="*70)
        logger.info("🏁 크롤러 종료")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"크롤링 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())