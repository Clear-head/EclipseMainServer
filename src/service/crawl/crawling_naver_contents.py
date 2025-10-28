import asyncio
from playwright.async_api import async_playwright, TimeoutError, Page
import sys, os
from dotenv import load_dotenv

load_dotenv(dotenv_path="src/.env")

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.logger.custom_logger import get_logger
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.crawling_manager import CrawlingManager


class NaverMapContentCrawler:
    """네이버 지도 콘텐츠(놀거리) 검색 크롤링 클래스"""
    
    # 콘텐츠 검색 키워드 목록
    CONTENT_KEYWORDS = [
        "서울 미술관",
        "서울 근교유적지",
        "서울 사격장",
        "서울 공방",
        "서울 박물관",
        "서울 클라이밍",
        "서울 동물카페"
    ]
    
    def __init__(self, headless: bool = False):
        self.logger = get_logger(__name__)
        self.headless = headless
        self.naver_map_url = "https://map.naver.com/v5/search"
        self.data_saver = StoreDataSaver()
        self.crawling_manager = CrawlingManager("콘텐츠")
        
        self.logger.info(f"✓ 네이버 지도 콘텐츠 크롤러 초기화 완료")
    
    async def crawl_by_keywords(
        self, 
        keywords: list = None,
        delay: int = 20
    ):
        """
        키워드 목록으로 네이버 지도 검색 후 크롤링 (제한 없음)
        
        Args:
            keywords: 검색 키워드 리스트 (None이면 기본 키워드 사용)
            delay: 크롤링 간 딜레이 (초)
        """
        keywords = keywords or self.CONTENT_KEYWORDS
        
        async with async_playwright() as p:
            # 네이버 크롤링용 브라우저
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--enable-features=ClipboardAPI']
            )
            context = await browser.new_context(
                permissions=['clipboard-read', 'clipboard-write']
            )
            page = await context.new_page()
            
            try:
                # 각 키워드별로 검색
                for keyword_idx, keyword in enumerate(keywords, 1):
                    self.logger.info(f"=" * 80)
                    self.logger.info(f"[키워드 {keyword_idx}/{len(keywords)}] '{keyword}' 크롤링 시작")
                    self.logger.info(f"=" * 80)
                    
                    # 키워드 시작할 때마다 중복 체크 초기화 (다른 키워드에서는 중복 허용)
                    keyword_crawled_names = set()
                    
                    # 키워드로 검색 및 크롤링 (크롤링하면서 바로 저장)
                    await self._search_and_crawl_all(
                        page, 
                        keyword,
                        delay=delay,
                        keyword_crawled_names=keyword_crawled_names
                    )
                    
                    self.logger.info(f"[키워드 {keyword_idx}/{len(keywords)}] '{keyword}' 완료")
                    
                    # 키워드 간 대기
                    if keyword_idx < len(keywords):
                        await asyncio.sleep(10)
                
                self.logger.info(f"=" * 80)
                self.logger.info(f"모든 키워드 크롤링 및 저장 완료!")
                self.logger.info(f"=" * 80)
                
            except Exception as e:
                self.logger.error(f"크롤링 중 오류 발생: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                await context.close()
                await browser.close()
    
    async def _search_and_crawl_all(
        self, 
        page: Page, 
        keyword: str,
        delay: int = 20,
        keyword_crawled_names: set = None
    ):
        """
        네이버 지도에서 키워드 검색 후 목록 클릭하여 크롤링 및 저장 (제한 없음)
        
        Args:
            page: Playwright Page 객체
            keyword: 검색 키워드
            delay: 크롤링 간 딜레이
            keyword_crawled_names: 현재 키워드에서 이미 크롤링한 이름들 (같은 키워드 내 중복 방지)
        """
        if keyword_crawled_names is None:
            keyword_crawled_names = set()
            
        try:
            # 네이버 지도 검색
            await page.goto(self.naver_map_url)
            await asyncio.sleep(2)
            
            # 검색어 입력
            search_input_selector = '.input_search'
            await page.wait_for_selector(search_input_selector)
            await page.fill(search_input_selector, '')
            await asyncio.sleep(0.5)
            
            await page.fill(search_input_selector, keyword)
            await page.press(search_input_selector, 'Enter')
            await asyncio.sleep(3)
            
            # 검색 결과 iframe 대기
            await page.wait_for_selector('iframe#searchIframe', timeout=10000)
            search_frame_locator = page.frame_locator('iframe#searchIframe')
            search_frame = page.frame('searchIframe')
            await asyncio.sleep(2)
            
            # 모든 페이지의 결과 크롤링 (제한 없음)
            crawled_count = 0
            page_num = 1
            
            while True:  # 🔥 제한 없이 계속 크롤링
                self.logger.info(f"  [{keyword}] {page_num}페이지 크롤링 중...")
                
                # 현재 페이지 스크롤하여 모든 목록 로드
                await self._scroll_to_load_all_items(search_frame_locator, search_frame)
                
                # 현재 페이지의 아이템 개수 확인
                item_selector = '#_pcmap_list_scroll_container > ul > li'
                items = await search_frame_locator.locator(item_selector).all()
                item_count = len(items)
                
                self.logger.info(f"  [{keyword}] {page_num}페이지: {item_count}개 아이템 발견")
                
                if item_count == 0:
                    self.logger.warning(f"  [{keyword}] {page_num}페이지에서 결과를 찾을 수 없습니다.")
                    break
                
                # 각 아이템 클릭하여 크롤링 및 저장
                for idx in range(item_count):
                    # 매번 목록을 다시 가져와야 함 (DOM 변경 때문)
                    items = await search_frame_locator.locator(item_selector).all()
                    
                    if idx >= len(items):
                        break
                    
                    item = items[idx]
                    
                    # 🔥 아이템 이름 및 클릭 요소 찾기 (우선순위: div.Dr2xO > div.pIwpC > a)
                    name = None
                    click_element = None
                    
                    try:
                        # 1차 시도: div.Dr2xO > div.pIwpC > a
                        first_selector = 'div.Dr2xO > div.pIwpC > a'
                        first_element = item.locator(first_selector).first
                        
                        if await first_element.count() > 0:
                            name = await first_element.inner_text(timeout=2000)
                            name = name.strip()
                            click_element = first_element
                            self.logger.debug(f"    [{idx+1}/{item_count}] 1차 선택자로 찾음: '{name}'")
                    except Exception as e:
                        self.logger.debug(f"    [{idx+1}/{item_count}] 1차 선택자 실패: {e}")
                    
                    # 2차 시도: 기존 방식
                    if not name or not click_element:
                        try:
                            name_selector = 'div.qbGlu > div.ouxiq > div.ApCpt > a > span.YwYLL'
                            name_element = item.locator(name_selector).first
                            
                            if await name_element.count() > 0:
                                name = await name_element.inner_text(timeout=2000)
                                name = name.strip()
                                
                                # 클릭 요소는 부모 <a> 태그
                                click_selector = 'div.qbGlu > div.ouxiq > div.ApCpt > a'
                                click_element = item.locator(click_selector).first
                                self.logger.debug(f"    [{idx+1}/{item_count}] 2차 선택자로 찾음: '{name}'")
                        except Exception as e:
                            self.logger.debug(f"    [{idx+1}/{item_count}] 2차 선택자 실패: {e}")
                    
                    # 이름을 찾지 못한 경우
                    if not name:
                        name = f"아이템 {idx+1}"
                        self.logger.warning(f"    [{idx+1}/{item_count}] 이름을 찾을 수 없음, 기본 이름 사용")
                    
                    # 같은 키워드 내에서만 중복 체크 (다른 키워드에서는 허용)
                    if name in keyword_crawled_names:
                        self.logger.info(f"    [{idx+1}/{item_count}] '{name}' - 현재 키워드에서 이미 크롤링됨, 건너뜀")
                        continue
                    
                    self.logger.info(f"    [{idx+1}/{item_count}] '{name}' 크롤링 시작...")
                    
                    # 아이템 클릭 (찾은 요소로 클릭)
                    try:
                        if click_element:
                            # 화면에 보이도록 스크롤
                            await click_element.scroll_into_view_if_needed()
                            await asyncio.sleep(0.3)
                            
                            # 클릭
                            await click_element.click(timeout=5000)
                            await asyncio.sleep(3)
                        else:
                            # 클릭 요소를 찾지 못한 경우 아이템 전체 클릭
                            await item.click(timeout=5000)
                            await asyncio.sleep(3)
                        
                    except Exception as click_error:
                        self.logger.error(f"    [{idx+1}/{item_count}] '{name}' 클릭 실패: {click_error}")
                        continue
                    
                    # entryIframe 대기 및 크롤링
                    try:
                        await page.wait_for_selector('iframe#entryIframe', timeout=10000)
                        entry_frame = page.frame_locator('iframe#entryIframe')
                        await asyncio.sleep(3)
                        
                        # 상세 정보 추출
                        extractor = StoreDetailExtractor(entry_frame, page)
                        store_data = await extractor.extract_all_details()
                        
                        if store_data:
                            actual_name = store_data[0]  # 추출된 실제 이름
                            keyword_crawled_names.add(actual_name)
                            crawled_count += 1
                            self.logger.info(f"    [{idx+1}/{item_count}] '{actual_name}' 크롤링 완료 ✓")
                            
                            # 🔥 크롤링 직후 바로 저장
                            try:
                                self.logger.info(f"    [{idx+1}/{item_count}] '{actual_name}' DB 저장 시작...")
                                result = await self._save_wrapper(crawled_count, item_count, store_data, actual_name)
                                
                                if result:
                                    success, msg = result
                                    if success:
                                        self.logger.info(f"    [{idx+1}/{item_count}] '{actual_name}' DB 저장 완료 ✓✓")
                                    else:
                                        self.logger.error(f"    [{idx+1}/{item_count}] '{actual_name}' DB 저장 실패: {msg}")
                                else:
                                    self.logger.error(f"    [{idx+1}/{item_count}] '{actual_name}' DB 저장 결과 없음")
                                    
                            except Exception as save_error:
                                self.logger.error(f"    [{idx+1}/{item_count}] '{actual_name}' DB 저장 중 오류: {save_error}")
                                import traceback
                                self.logger.error(traceback.format_exc())
                        else:
                            self.logger.error(f"    [{idx+1}/{item_count}] '{name}' 정보 추출 실패")
                        
                    except TimeoutError:
                        self.logger.error(f"    [{idx+1}/{item_count}] '{name}' entryIframe을 찾을 수 없음")
                    except Exception as crawl_error:
                        self.logger.error(f"    [{idx+1}/{item_count}] '{name}' 크롤링 중 오류: {crawl_error}")
                    
                    # 딜레이
                    if idx < item_count - 1:
                        await asyncio.sleep(delay)
                
                self.logger.info(f"  [{keyword}] {page_num}페이지 완료 (누적 {crawled_count}개)")
                
                # 다음 페이지로 이동
                has_next = await self._go_to_next_page(search_frame_locator)
                
                if not has_next:
                    self.logger.info(f"  [{keyword}] 마지막 페이지 도달 (총 {crawled_count}개 크롤링 완료)")
                    break
                
                page_num += 1
                await asyncio.sleep(3)
            
        except TimeoutError:
            self.logger.error(f"'{keyword}' 검색 결과를 찾을 수 없습니다.")
        except Exception as e:
            self.logger.error(f"'{keyword}' 검색 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def _scroll_to_load_all_items(self, search_frame_locator, search_frame):
        """
        검색 결과 목록을 조금씩 천천히 스크롤하여 모든 아이템 로드
        """
        try:
            scroll_container_selector = '#_pcmap_list_scroll_container'
            
            # 스크롤 컨테이너 대기
            await search_frame_locator.locator(scroll_container_selector).wait_for(state='visible', timeout=5000)
            
            prev_count = 0
            same_count = 0
            max_same_count = 10
            scroll_step = 500
            
            for scroll_attempt in range(200):
                # 현재 아이템 개수
                items = await search_frame_locator.locator(f'{scroll_container_selector} > ul > li').all()
                current_count = len(items)
                
                if current_count == prev_count:
                    same_count += 1
                    if same_count >= max_same_count:
                        self.logger.info(f"      스크롤 완료: 총 {current_count}개 아이템 로드")
                        break
                else:
                    same_count = 0
                    if scroll_attempt % 10 == 0:
                        self.logger.info(f"      스크롤 중... 현재 {current_count}개 로드됨")
                
                prev_count = current_count
                
                try:
                    await search_frame.evaluate(f'''
                        () => {{
                            const container = document.querySelector('{scroll_container_selector}');
                            if (container) {{
                                container.scrollBy({{
                                    top: {scroll_step},
                                    behavior: 'smooth'
                                }});
                            }}
                        }}
                    ''')
                except:
                    pass
                
                await asyncio.sleep(0.5)
            
        except Exception as e:
            self.logger.warning(f"스크롤 중 오류 (계속 진행): {e}")
    
    async def _go_to_next_page(self, search_frame_locator) -> bool:
        """다음 페이지로 이동"""
        try:
            next_button_selector = 'a.eUTV2'
            next_button = search_frame_locator.locator(next_button_selector)
            
            if await next_button.count() > 0:
                is_disabled = await next_button.get_attribute('aria-disabled')
                
                if is_disabled == 'true':
                    return False
                
                await next_button.click()
                await asyncio.sleep(2)
                
                self.logger.info(f"      다음 페이지로 이동")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.warning(f"다음 페이지 이동 중 오류: {e}")
            return False
    
    async def _save_wrapper(self, idx: int, total: int, store_data: tuple, store_name: str):
        """저장 래퍼"""
        return await self.data_saver.save_store_data(
            idx=idx,
            total=total,
            store_data=store_data,
            store_name=store_name,
            log_prefix="콘텐츠"
        )


async def main():
    """메인 함수"""
    logger = get_logger(__name__)
    
    headless_mode = False
    crawl_delay = 20
    
    logger.info("=" * 80)
    logger.info("네이버 지도 콘텐츠 크롤링 시작")
    logger.info("=" * 80)
    
    try:
        crawler = NaverMapContentCrawler(headless=headless_mode)
        
        await crawler.crawl_by_keywords(
            keywords=None,
            delay=crawl_delay
        )
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ 모든 크롤링 완료!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == '__main__':
    asyncio.run(main())