"""
네이버 지도 콘텐츠(놀거리) 검색 크롤링 모듈 (이름 기반 매칭 + 최적화)
브라우저 재시작 시 순서가 바뀌어도 이름으로 찾아서 크롤링
검색 상태 유지로 불필요한 스크롤 제거
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
    """네이버 지도 콘텐츠(놀거리) 검색 크롤링 클래스 (이름 기반 매칭)"""
    
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
        """키워드 목록으로 크롤링 (이름 기반 매칭)"""
        keywords = keywords or self.CONTENT_KEYWORDS
        
        async with async_playwright() as p:
            browser = await OptimizedBrowserManager.create_optimized_browser(p, self.headless)
            
            try:
                self.logger.info(f"총 {len(keywords)}개 키워드 크롤링 시작 (이름 기반 매칭)")
                
                for keyword_idx, keyword in enumerate(keywords, 1):
                    self.logger.info(f"[키워드 {keyword_idx}/{len(keywords)}] '{keyword}' 크롤링 시작")
                    
                    # 키워드별로 페이지 단위 처리
                    await self._crawl_keyword_by_pages(browser, keyword, delay)
                    
                    self.logger.info(f"[키워드 {keyword_idx}/{len(keywords)}] '{keyword}' 완료\n")
                    
                    if keyword_idx < len(keywords):
                        import random
                        rest_time = random.uniform(40, 60)
                        self.logger.info(f"키워드 완료, {rest_time:.0f}초 휴식...\n")
                        await asyncio.sleep(rest_time)
                
                self.logger.info(f"모든 키워드 크롤링 완료!")
                self.logger.info(f"성공: {self.success_count}개")
                self.logger.info(f"실패: {self.fail_count}개")
                
            except Exception as e:
                self.logger.error(f"크롤링 중 오류: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                await browser.close()
    
    async def _crawl_keyword_by_pages(self, browser, keyword: str, delay: int):
        """
        키워드별로 배치 단위로 크롤링 (이름 기반)
        
        1. 전체 아이템의 이름 목록을 먼저 수집
        2. 배치 단위로 브라우저 재시작
        3. 이름으로 아이템을 찾아서 크롤링
        """
        # ✅ 1단계: 전체 아이템의 이름 목록 수집
        total_items, total_pages, name_list = await self._get_total_items_with_names(browser, keyword)
        
        if total_items == 0:
            self.logger.warning(f"'{keyword}' 결과 없음")
            return
        
        self.logger.info(f"'{keyword}' 총 {total_items}개 ({total_pages}페이지)")
        self.logger.info(f"수집된 이름: {len(name_list)}개\n")
        
        # ✅ 2단계: 배치 단위로 크롤링
        for batch_start in range(0, total_items, self.RESTART_INTERVAL):
            batch_end = min(batch_start + self.RESTART_INTERVAL, total_items)
            
            batch_num = batch_start // self.RESTART_INTERVAL + 1
            total_batches = (total_items + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL
            
            self.logger.info(f"[{keyword}] 배치 {batch_num}/{total_batches}: {batch_start+1}~{batch_end}/{total_items}")
            
            # 새 컨텍스트 생성 (브라우저 재시작)
            context = await OptimizedBrowserManager.create_stealth_context(browser)
            page = await context.new_page()
            
            try:
                # 배치 처리 (CrawlingManager 사용)
                await self._process_batch_with_crawling_manager(
                    page, keyword, batch_start, batch_end, name_list, total_items, delay
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
                    self.logger.info(f"배치 완료, {rest_time:.0f}초 휴식...\n")
                    await asyncio.sleep(rest_time)
    
    async def _get_total_items_with_names(self, browser, keyword: str) -> tuple:
        """
        전체 아이템 개수, 페이지 수, 이름 목록 수집
        
        Returns:
            Tuple[int, int, List[str]]: (전체 아이템 수, 전체 페이지 수, 이름 목록)
        """
        context = await browser.new_context()
        page = await context.new_page()
        
        name_list = []
        
        try:
            self.logger.info(f"'{keyword}' 전체 이름 목록 수집 중...")
            
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
                return 0, 0, []
            
            await asyncio.sleep(3)
            
            # 페이지별로 스크롤하여 전체 이름 수집
            total_items = 0
            page_num = 1
            item_selector = '#_pcmap_list_scroll_container > ul > li'
            
            while True:
                # 현재 페이지 스크롤
                await SearchResultScroller.scroll_current_page(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                # 현재 페이지의 모든 아이템 가져오기
                items = await search_frame_locator.locator(item_selector).all()
                item_count = len(items)
                
                if item_count == 0:
                    break
                
                # 각 아이템의 이름 추출
                for idx, item in enumerate(items):
                    try:
                        name = await self._extract_item_name(item, idx, item_count)
                        name_list.append(name)
                        total_items += 1
                    except Exception as e:
                        self.logger.warning(f"페이지 {page_num}, 아이템 {idx} 이름 추출 실패: {e}")
                        name_list.append(f"아이템 {total_items + 1}")
                        total_items += 1
                
                # 다음 페이지 확인
                has_next = await PageNavigator.go_to_next_page_naver(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                if not has_next:
                    break
                
                page_num += 1
                await asyncio.sleep(2)
            
            self.logger.info(f"총 {total_items}개 이름 수집 완료 ({page_num}페이지)")
            return total_items, page_num, name_list
            
        except Exception as e:
            self.logger.error(f"'{keyword}' 이름 목록 수집 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0, 0, []
        finally:
            await context.close()
    
    async def _process_batch_with_crawling_manager(
        self,
        page: Page,
        keyword: str,
        batch_start: int,
        batch_end: int,
        name_list: list,
        total: int,
        delay: int
    ):
        """
        배치 단위 크롤링 (CrawlingManager 사용 + 검색 상태 유지)
        
        ✅ 한 번 검색 후 상태 유지하며 매장별로 크롤링
        """
        try:
            # ✅ 네이버 지도 검색 (한 번만)
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
            
            # ✅ 전체 페이지 미리 로드 (한 번만)
            await self._load_all_pages(search_frame_locator, search_frame)
            
            item_selector = '#_pcmap_list_scroll_container > ul > li'
            
            # 이 배치에서 처리할 이름들
            batch_names = name_list[batch_start:batch_end]
            
            # 이미 처리한 이름들 (중복 방지)
            processed_names = set()
            
            # 매장 정보 리스트 생성 (CrawlingManager용)
            stores = []
            for idx, target_name in enumerate(batch_names):
                stores.append({
                    'name': target_name,
                    'global_idx': batch_start + idx
                })
            
            # ✅ CrawlingManager로 크롤링 + 저장
            crawling_manager = CrawlingManager("콘텐츠")
            
            await crawling_manager.execute_crawling_with_save(
                stores=stores,
                crawl_func=lambda store, idx, total_stores: self._crawl_single_item_wrapper(
                    page, search_frame_locator, item_selector, store, total, processed_names
                ),
                save_func=lambda idx, total_stores, store_data_tuple, store_name: self._save_wrapper(
                    idx, store_data_tuple, batch_start, total  # ✅ idx와 batch_start 전달
                ),
                delay=delay
            )
            
            # 성공/실패 카운트 업데이트
            self.success_count += crawling_manager.success_count
            self.fail_count += crawling_manager.fail_count
            
            return batch_end
            
        except Exception as e:
            self.logger.error(f"배치 처리 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0
    
    async def _load_all_pages(self, search_frame_locator, search_frame):
        """
        전체 페이지 미리 로드 (한 번만)
        
        모든 페이지를 순회하며 스크롤하여 전체 DOM 로드
        """
        try:
            self.logger.info("전체 페이지 로드 중...")
            
            current_page = 1
            
            while True:
                # 현재 페이지 스크롤
                await SearchResultScroller.scroll_current_page(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                # 다음 페이지 확인
                has_next = await PageNavigator.go_to_next_page_naver(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                if not has_next:
                    break
                
                current_page += 1
                await asyncio.sleep(2)
            
            # ✅ 1페이지로 돌아가기
            await self._go_to_first_page(search_frame_locator, search_frame)
            
            self.logger.info(f"{current_page}페이지 로드 완료\n")
            
        except Exception as e:
            self.logger.warning(f"전체 페이지 로드 중 오류 (계속 진행): {e}")
    
    async def _crawl_single_item_wrapper(
        self,
        page: Page,
        search_frame_locator,
        item_selector: str,
        store: dict,
        total: int,
        processed_names: set
    ):
        """
        CrawlingManager용 크롤링 래퍼
        
        ✅ 검색 상태를 유지하며 매장 크롤링
        """
        target_name = store['name']
        global_idx = store['global_idx']
        
        return await self._crawl_single_item_by_name(
            page=page,
            search_frame_locator=search_frame_locator,
            item_selector=item_selector,
            target_name=target_name,
            global_idx=global_idx,
            total=total,
            processed_names=processed_names
        )
    
    async def _save_wrapper(
        self, 
        idx: int,  # ✅ CrawlingManager가 전달하는 배치 내 인덱스 (1부터 시작)
        store_data_tuple, 
        batch_start: int,  # ✅ 배치 시작 인덱스
        total: int
    ) -> tuple:
        """CrawlingManager용 저장 래퍼"""
        if store_data_tuple is None:
            return (False, "크롤링 실패")
        
        store_data, actual_name = store_data_tuple
        
        # ✅ 전체 인덱스 계산: batch_start + idx
        global_idx = batch_start + idx
        
        return await self.data_saver.save_store_data(
            idx=global_idx,  # ✅ 실제 인덱스 전달
            total=total,
            store_data=store_data,
            store_name=actual_name,
            log_prefix="콘텐츠"
        )
    
    async def _crawl_single_item_by_name(
        self,
        page: Page,
        search_frame_locator,
        item_selector: str,
        target_name: str,
        global_idx: int,
        total: int,
        processed_names: set
    ):
        """
        이름으로 아이템을 찾아 크롤링 (검색 상태 유지)
        
        ✅ 현재 페이지에 없으면 1페이지부터 전체 순회
        """
        try:
            search_frame = page.frame('searchIframe')
            
            if not search_frame:
                self.logger.error("searchIframe을 찾을 수 없습니다.")
                return None
            
            # ✅ 1단계: 현재 페이지에서 먼저 찾기
            items = await search_frame_locator.locator(item_selector).all()
            
            for idx, current_item in enumerate(items):
                try:
                    current_name = await self._extract_item_name(current_item, idx, len(items))
                    
                    if current_name == target_name and current_name not in processed_names:
                        self.logger.info(f"[{global_idx+1}/{total}] '{target_name}' 발견 (현재 페이지)")
                        
                        # 크롤링 실행
                        result = await self._execute_crawling(
                            page, current_item, target_name, global_idx, total, 
                            processed_names, idx
                        )
                        
                        if result:
                            return result
                        else:
                            return None
                except:
                    continue
            
            # ✅ 2단계: 현재 페이지에 없으면 1페이지부터 전체 순회
            self.logger.info(f"[{global_idx+1}/{total}] '{target_name}' 현재 페이지에 없음, 전체 검색 시작")
            
            # 1페이지로 이동
            await self._go_to_first_page(search_frame_locator, search_frame)
            await asyncio.sleep(1)
            
            current_page = 1
            max_pages = 50
            
            while current_page <= max_pages:
                # 현재 페이지의 모든 아이템 가져오기
                items = await search_frame_locator.locator(item_selector).all()
                
                # 현재 페이지에서 타겟 이름 찾기
                for idx, current_item in enumerate(items):
                    try:
                        current_name = await self._extract_item_name(current_item, idx, len(items))
                        
                        # 타겟 이름 발견 & 아직 처리 안 했으면
                        if current_name == target_name and current_name not in processed_names:
                            self.logger.info(f"[{global_idx+1}/{total}] '{target_name}' 발견 (페이지 {current_page})")
                            
                            # 크롤링 실행
                            result = await self._execute_crawling(
                                page, current_item, target_name, global_idx, total, 
                                processed_names, idx
                            )
                            
                            if result:
                                return result
                            else:
                                return None
                    
                    except Exception as e:
                        continue
                
                # 다음 페이지로 이동
                has_next = await PageNavigator.go_to_next_page_naver(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                if not has_next:
                    break
                
                current_page += 1
                await asyncio.sleep(2)
            
            # 끝까지 찾았는데 없음
            self.logger.error(f"[{global_idx+1}/{total}] '{target_name}' 아이템을 찾을 수 없음")
            return None
            
        except Exception as e:
            self.logger.error(f"[{global_idx+1}/{total}] '{target_name}' 크롤링 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    async def _execute_crawling(
        self,
        page: Page,
        current_item,
        target_name: str,
        global_idx: int,
        total: int,
        processed_names: set,
        idx: int
    ):
        """
        실제 크롤링 실행 (중복 코드 제거)
        """
        try:
            # 클릭 요소 찾기
            click_element = await self._find_click_element(current_item, idx)
            
            if not click_element:
                self.logger.error(f"[{global_idx+1}/{total}] '{target_name}' 클릭 요소 없음")
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
                    
                    # 처리 완료 표시
                    processed_names.add(target_name)
                    
                    # 리소스 정리
                    await OptimizedBrowserManager.clear_page_resources(page)
                    
                    # ✅ 검색 결과로 돌아가기 (뒤로 가기)
                    await page.go_back()
                    await asyncio.sleep(2)
                    
                    return (store_data, actual_name)
                else:
                    self.logger.error(f"[{global_idx+1}/{total}] '{target_name}' 정보 추출 실패")
                    return None
                    
            except TimeoutError:
                self.logger.error(f"[{global_idx+1}/{total}] '{target_name}' entryIframe 타임아웃")
                return None
        
        except Exception as e:
            self.logger.error(f"[{global_idx+1}/{total}] '{target_name}' 크롤링 실행 중 오류: {e}")
            return None
    
    async def _go_to_first_page(self, search_frame_locator, search_frame):
        """페이지네이션을 1페이지로 이동"""
        try:
            pagination_selector = 'div.zRM9F > a'
            first_page_button = search_frame_locator.locator(pagination_selector).filter(has_text="1").first
            
            if await first_page_button.count() > 0:
                await first_page_button.click()
                await asyncio.sleep(2)
                self.logger.debug("1페이지로 이동")
        
        except Exception as e:
            self.logger.debug(f"1페이지 이동 실패: {e}")
    
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
        
        return item


async def main():
    """메인 함수"""
    logger = get_logger(__name__)
    
    logger.info("네이버 지도 콘텐츠 크롤러 시작 (이름 기반 매칭)")
    
    try:
        crawler = NaverMapContentCrawler(headless=False)
        
        await crawler.crawl_by_keywords(
            keywords=None,
            delay=15
        )
        
        logger.info("크롤러 종료")
        
    except Exception as e:
        logger.error(f"크롤링 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())