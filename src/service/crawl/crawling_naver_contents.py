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
        "서울 동물카페",
        "서울 공방",
        "서울 사격장",
        "서울 미술관",
        "서울 근교유적지",
        "서울 박물관",
        "서울 클라이밍",
    ]
    
    def __init__(self, headless: bool = False):
        self.logger = get_logger(__name__)
        self.headless = headless
        self.naver_map_url = "https://map.naver.com/v5/search"
        self.data_saver = StoreDataSaver()
        self.crawling_manager = CrawlingManager("콘텐츠")
        
        # self.logger.info(f"네이버 지도 콘텐츠 크롤러 초기화 완료")
    
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
                    # self.logger.info(f"=" * 80)
                    self.logger.info(f"[키워드 {keyword_idx}/{len(keywords)}] '{keyword}' 크롤링 시작")
                    # self.logger.info(f"=" * 80)
                    
                    # 키워드로 검색 및 크롤링
                    await self._search_and_crawl_all(
                        page, 
                        keyword,
                        delay=delay
                    )
                    
                    self.logger.info(f"[키워드 {keyword_idx}/{len(keywords)}] '{keyword}' 완료")
                    
                    # 키워드 간 대기
                    if keyword_idx < len(keywords):
                        await asyncio.sleep(10)
                
                # self.logger.info(f"=" * 80)
                self.logger.info(f"모든 키워드 크롤링 및 저장 완료!")
                # self.logger.info(f"=" * 80)
                
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
        delay: int = 20
    ):
        """
        네이버 지도에서 키워드 검색 후 목록 클릭하여 크롤링 및 저장 (제한 없음)
        
        Args:
            page: Playwright Page 객체
            keyword: 검색 키워드
            delay: 크롤링 간 딜레이
        """
        try:
            # 네이버 지도 검색
            await page.goto(self.naver_map_url, wait_until='domcontentloaded')
            await asyncio.sleep(3)
            
            # 검색어 입력
            search_input_selector = '.input_search'
            await page.wait_for_selector(search_input_selector)
            await page.fill(search_input_selector, '')
            await asyncio.sleep(0.5)
            
            await page.fill(search_input_selector, keyword)
            await page.press(search_input_selector, 'Enter')
            await asyncio.sleep(5)
            
            # 검색 결과 iframe 대기
            await page.wait_for_selector('iframe#searchIframe', timeout=10000)
            search_frame_locator = page.frame_locator('iframe#searchIframe')
            search_frame = page.frame('searchIframe')
            await asyncio.sleep(3)
            
            # 페이지별로 크롤링
            page_num = 1
            total_crawled = 0
            
            while True:  # 🔥 제한 없이 계속 크롤링
                self.logger.info(f"  [{keyword}] {page_num}페이지 크롤링 시작...")
                
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
                
                # 🔥 현재 페이지의 아이템 정보 수집
                page_items = []
                for idx in range(item_count):
                    items = await search_frame_locator.locator(item_selector).all()
                    
                    if idx >= len(items):
                        break
                    
                    item = items[idx]
                    
                    # 아이템 이름 추출
                    name = await self._extract_item_name(item, idx, item_count)
                    
                    # 아이템 정보 저장
                    page_items.append({
                        'name': name,
                        'page_num': page_num,
                        'idx': idx,
                        'total_in_page': item_count
                    })
                
                # 🔥 현재 페이지의 아이템들을 병렬로 크롤링
                if page_items:
                    self.logger.info(f"  [{keyword}] {page_num}페이지 {len(page_items)}개 아이템 크롤링 중...")
                    
                    await self.crawling_manager.execute_crawling_with_save(
                        stores=page_items,
                        crawl_func=lambda item, i, t: self._crawl_single_item(
                            page, search_frame_locator, item_selector, item
                        ),
                        save_func=self._save_wrapper,
                        delay=delay
                    )
                    
                    total_crawled += len(page_items)
                
                self.logger.info(f"  [{keyword}] {page_num}페이지 완료 (누적 {total_crawled}개)")
                
                # 다음 페이지로 이동
                has_next = await self._go_to_next_page(search_frame_locator, search_frame)
                
                if not has_next:
                    self.logger.info(f"  [{keyword}] 마지막 페이지 도달 (총 {total_crawled}개 크롤링 완료)")
                    break
                
                page_num += 1
                await asyncio.sleep(3)
            
        except TimeoutError:
            self.logger.error(f"'{keyword}' 검색 결과를 찾을 수 없습니다.")
        except Exception as e:
            self.logger.error(f"'{keyword}' 검색 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def _extract_item_name(self, item, idx: int, item_count: int) -> str:
        """아이템 이름 추출 (4가지 선택자 시도)"""
        name = None
        
        try:
            # 1차 시도: div.Dr2xO > div.pIwpC > a > span.CMy2_
            first_name_selector = 'div.Dr2xO > div.pIwpC > a > span.CMy2_'
            first_name_element = item.locator(first_name_selector).first
            
            if await first_name_element.count() > 0:
                name = await first_name_element.inner_text(timeout=2000)
                name = name.strip()
                # self.logger.debug(f"    [{idx+1}/{item_count}] 1차 선택자로 찾음: '{name}'")
        except Exception as e:
            self.logger.debug(f"    [{idx+1}/{item_count}] 1차 선택자 실패: {e}")
        
        # 2차 시도
        if not name:
            try:
                name_selector = 'div.qbGlu > div.ouxiq > div.ApCpt > a > span.YwYLL'
                name_element = item.locator(name_selector).first
                
                if await name_element.count() > 0:
                    name = await name_element.inner_text(timeout=2000)
                    name = name.strip()
                    # self.logger.debug(f"    [{idx+1}/{item_count}] 2차 선택자로 찾음: '{name}'")
            except Exception as e:
                self.logger.debug(f"    [{idx+1}/{item_count}] 2차 선택자 실패: {e}")
        
        # 3차 시도
        if not name:
            try:
                third_name_selector = 'div.Np1CD > div:nth-child(2) > div.SbNoJ > a > span.t3s7S'
                third_name_element = item.locator(third_name_selector).first
                
                if await third_name_element.count() > 0:
                    name = await third_name_element.inner_text(timeout=2000)
                    name = name.strip()
                    # self.logger.debug(f"    [{idx+1}/{item_count}] 3차 선택자로 찾음: '{name}'")
            except Exception as e:
                self.logger.debug(f"    [{idx+1}/{item_count}] 3차 선택자 실패: {e}")
        
        # 4차 시도: div.Np1CD > div > div.SbNoJ > a > span.t3s7S
        if not name:
            try:
                fourth_name_selector = 'div.Np1CD > div > div.SbNoJ > a > span.t3s7S'
                fourth_name_element = item.locator(fourth_name_selector).first
                
                if await fourth_name_element.count() > 0:
                    name = await fourth_name_element.inner_text(timeout=2000)
                    name = name.strip()
                    # self.logger.debug(f"    [{idx+1}/{item_count}] 4차 선택자로 찾음: '{name}'")
            except Exception as e:
                self.logger.debug(f"    [{idx+1}/{item_count}] 4차 선택자 실패: {e}")
        
        if not name:
            name = f"아이템 {idx+1}"
            self.logger.warning(f"    [{idx+1}/{item_count}] 이름을 찾을 수 없음, 기본 이름 사용")
        
        return name
    
    async def _crawl_single_item(
        self,
        page: Page,
        search_frame_locator,
        item_selector: str,
        item_info: dict
    ):
        """
        단일 아이템 크롤링
        
        Args:
            page: 메인 페이지
            search_frame_locator: 검색 frame locator
            item_selector: 아이템 선택자
            item_info: 아이템 정보 dict
        
        Returns:
            Tuple: (store_data, actual_name) 또는 None
        """
        name = item_info['name']
        idx = item_info['idx']
        
        try:
            # 아이템 다시 찾기
            items = await search_frame_locator.locator(item_selector).all()
            
            if idx >= len(items):
                self.logger.error(f"'{name}' 아이템을 찾을 수 없습니다.")
                return None
            
            item = items[idx]
            
            # 클릭 요소 찾기
            click_element = await self._find_click_element(item, idx)
            
            if not click_element:
                self.logger.error(f"'{name}' 클릭 요소를 찾을 수 없습니다.")
                return None
            
            # 클릭
            try:
                await click_element.scroll_into_view_if_needed()
                await asyncio.sleep(0.3)
                await click_element.click(timeout=5000)
                await asyncio.sleep(3)
            except Exception as click_error:
                self.logger.error(f"'{name}' 클릭 실패: {click_error}")
                return None
            
            # entryIframe 대기 및 크롤링
            try:
                await page.wait_for_selector('iframe#entryIframe', timeout=10000)
                entry_frame = page.frame_locator('iframe#entryIframe')
                await asyncio.sleep(3)
                
                # 상세 정보 추출
                extractor = StoreDetailExtractor(entry_frame, page)
                store_data = await extractor.extract_all_details()
                
                if store_data:
                    actual_name = store_data[0]
                    return (store_data, actual_name)
                else:
                    self.logger.error(f"'{name}' 정보 추출 실패")
                    return None
                
            except TimeoutError:
                self.logger.error(f"'{name}' entryIframe을 찾을 수 없음")
                return None
            except Exception as crawl_error:
                self.logger.error(f"'{name}' 크롤링 중 오류: {crawl_error}")
                return None
                
        except Exception as e:
            self.logger.error(f"'{name}' 크롤링 중 예외: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    async def _find_click_element(self, item, idx: int):
        """클릭 요소 찾기 (4가지 선택자 시도)"""
        # 1차 시도
        try:
            first_link_selector = 'div.Dr2xO > div.pIwpC > a'
            first_element = item.locator(first_link_selector).first
            if await first_element.count() > 0:
                return first_element
        except:
            pass
        
        # 2차 시도
        try:
            click_selector = 'div.qbGlu > div.ouxiq > div.ApCpt > a'
            second_element = item.locator(click_selector).first
            if await second_element.count() > 0:
                return second_element
        except:
            pass
        
        # 3차 시도
        try:
            third_link_selector = 'div.Np1CD > div:nth-child(2) > div.SbNoJ > a'
            third_element = item.locator(third_link_selector).first
            if await third_element.count() > 0:
                return third_element
        except:
            pass
        
        # 4차 시도
        try:
            fourth_link_selector = 'div.Np1CD > div > div.SbNoJ > a'
            fourth_element = item.locator(fourth_link_selector).first
            if await fourth_element.count() > 0:
                return fourth_element
        except:
            pass
        
        # 모두 실패하면 아이템 전체
        return item
    
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
                        # self.logger.info(f"      스크롤 완료: 총 {current_count}개 아이템 로드")
                        break
                else:
                    same_count = 0
                    if scroll_attempt % 10 == 0:
                        # self.logger.info(f"      스크롤 중... 현재 {current_count}개 로드됨")
                
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
    
    async def _go_to_next_page(self, search_frame_locator, search_frame) -> bool:
        """다음 페이지로 이동 (span 텍스트가 '다음페이지'인 버튼만 선택)"""
        try:
            # 모든 페이지 버튼 찾기
            next_button_selector = 'a.eUTV2'
            next_buttons = await search_frame_locator.locator(next_button_selector).all()
            
            if len(next_buttons) == 0:
                return False
            
            # "다음페이지" 텍스트를 가진 버튼 찾기
            for button in next_buttons:
                try:
                    span_text = await button.locator('span').inner_text(timeout=1000)
                    
                    if span_text and '다음페이지' in span_text:
                        # aria-disabled 체크
                        is_disabled = await button.get_attribute('aria-disabled')
                        
                        if is_disabled == 'true':
                            return False
                        
                        # 다음 페이지 클릭
                        await button.click()
                        await asyncio.sleep(2)
                        
                        # 스크롤을 맨 위로 초기화
                        scroll_container_selector = '#_pcmap_list_scroll_container'
                        try:
                            await search_frame.evaluate(f'''
                                () => {{
                                    const container = document.querySelector('{scroll_container_selector}');
                                    if (container) {{
                                        container.scrollTop = 0;
                                    }}
                                }}
                            ''')
                            await asyncio.sleep(1)
                        except:
                            pass
                        
                        # self.logger.info(f"      다음 페이지로 이동")
                        return True
                except:
                    continue
            
            # "다음페이지" 버튼을 찾지 못함
            return False
                
        except Exception as e:
            self.logger.warning(f"다음 페이지 이동 중 오류: {e}")
            return False
    
    async def _save_wrapper(self, idx: int, total: int, store_data_tuple, store_name: str):
        """
        저장 래퍼
        
        Args:
            store_data_tuple: (store_data, actual_name) 튜플 또는 None
        """
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


async def main():
    """메인 함수"""
    logger = get_logger(__name__)
    
    headless_mode = False
    crawl_delay = 10
    
    # logger.info("=" * 80)
    logger.info("네이버 지도 콘텐츠 크롤링 시작")
    # logger.info("=" * 80)
    
    try:
        crawler = NaverMapContentCrawler(headless=headless_mode)
        
        await crawler.crawl_by_keywords(
            keywords=None,
            delay=crawl_delay
        )
        
        # logger.info("")
        # logger.info("=" * 80)
        logger.info("모든 크롤링 완료!")
        # logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())