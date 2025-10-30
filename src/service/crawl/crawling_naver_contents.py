"""
네이버 지도 콘텐츠(놀거리) 검색 크롤링 모듈 (메모리 최적화 + 봇 우회 + 병렬 처리)
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
    """네이버 지도 콘텐츠(놀거리) 검색 크롤링 클래스"""
    
    CONTENT_KEYWORDS = [
        "서울 동물카페",
        "서울 공방",
        "서울 사격장",
        "서울 미술관",
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
        """키워드 목록으로 병렬 크롤링"""
        keywords = keywords or self.CONTENT_KEYWORDS
        
        async with async_playwright() as p:
            browser = await OptimizedBrowserManager.create_optimized_browser(p, self.headless)
            
            try:
                self.logger.info(f"\n{'='*70}")
                self.logger.info(f"📊 총 {len(keywords)}개 키워드 크롤링 시작 (병렬 처리)")
                self.logger.info(f"{'='*70}\n")
                
                for keyword_idx, keyword in enumerate(keywords, 1):
                    self.logger.info(f"\n{'='*70}")
                    self.logger.info(f"[키워드 {keyword_idx}/{len(keywords)}] '{keyword}' 크롤링 시작")
                    self.logger.info(f"{'='*70}\n")
                    
                    # 전체 아이템 목록 수집
                    all_items = await self._collect_items_by_keyword(browser, keyword)
                    
                    if not all_items:
                        self.logger.warning(f"'{keyword}' 결과 없음")
                        continue
                    
                    total = len(all_items)
                    self.logger.info(f"✅ '{keyword}' 총 {total}개 수집 완료")
                    
                    # 배치 단위로 병렬 크롤링
                    for batch_start in range(0, total, self.RESTART_INTERVAL):
                        batch_end = min(batch_start + self.RESTART_INTERVAL, total)
                        batch = all_items[batch_start:batch_end]
                        
                        batch_num = batch_start // self.RESTART_INTERVAL + 1
                        total_batches = (total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL
                        
                        self.logger.info(f"\n🔄 [{keyword}] 배치 {batch_num}/{total_batches}: {batch_start+1}~{batch_end}/{total}")
                        
                        context = await OptimizedBrowserManager.create_stealth_context(browser)
                        page = await context.new_page()
                        
                        try:
                            await self._process_batch_parallel(
                                page, keyword, batch, batch_start, total, delay
                            )
                        except Exception as e:
                            self.logger.error(f"배치 처리 중 오류: {e}")
                            import traceback
                            self.logger.error(traceback.format_exc())
                        finally:
                            await context.close()
                            await asyncio.sleep(3)
                            
                            if batch_end < total:
                                import random
                                rest_time = random.uniform(20, 40)
                                self.logger.info(f"🛌 배치 완료, {rest_time:.0f}초 휴식...\n")
                                await asyncio.sleep(rest_time)
                    
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
    
    async def _collect_items_by_keyword(self, browser, keyword: str) -> list:
        """키워드로 전체 아이템 목록 수집"""
        context = await browser.new_context()
        page = await context.new_page()
        
        all_items = []
        
        try:
            await page.goto(self.naver_map_url, wait_until='domcontentloaded')
            await asyncio.sleep(3)
            
            search_input_selector = '.input_search'
            await page.wait_for_selector(search_input_selector)
            await page.fill(search_input_selector, '')
            await asyncio.sleep(0.5)
            
            await page.fill(search_input_selector, keyword)
            await page.press(search_input_selector, 'Enter')
            await asyncio.sleep(5)
            
            await page.wait_for_selector('iframe#searchIframe', timeout=10000)
            search_frame_locator = page.frame_locator('iframe#searchIframe')
            search_frame = page.frame('searchIframe')
            
            if not search_frame:
                return []
            
            await asyncio.sleep(3)
            
            page_num = 1
            
            while True:
                self.logger.info(f"  '{keyword}' {page_num}페이지 수집 중...")
                
                item_count = await SearchResultScroller.scroll_current_page(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                if item_count == 0:
                    break
                
                item_selector = '#_pcmap_list_scroll_container > ul > li'
                items = await search_frame_locator.locator(item_selector).all()
                
                for idx, item in enumerate(items):
                    try:
                        name = await self._extract_item_name(item, idx, len(items))
                        
                        all_items.append({
                            'name': name,
                            'keyword': keyword,
                            'page': page_num,
                            'idx': idx
                        })
                        
                    except Exception as e:
                        self.logger.warning(f"  아이템 {idx+1} 정보 추출 실패: {e}")
                        continue
                
                self.logger.info(f"  '{keyword}' {page_num}페이지: {len(items)}개 수집 (누적 {len(all_items)}개)")
                
                has_next = await PageNavigator.go_to_next_page_naver(
                    search_frame_locator=search_frame_locator,
                    search_frame=search_frame
                )
                
                if not has_next:
                    self.logger.info(f"  '{keyword}' 마지막 페이지 도달")
                    break
                
                page_num += 1
                await asyncio.sleep(3)
                
        except Exception as e:
            self.logger.error(f"'{keyword}' 목록 수집 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            await context.close()
        
        return all_items
    
    async def _process_batch_parallel(
        self, 
        page: Page, 
        keyword: str,
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
            crawling_manager = CrawlingManager("콘텐츠")
            
            await crawling_manager.execute_crawling_with_save(
                stores=batch,
                crawl_func=lambda item, i, t: self._search_and_crawl_item(
                    page, item['name'], keyword
                ),
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
    
    async def _search_and_crawl_item(self, page: Page, name: str, keyword: str):
        """네이버 지도에서 검색하여 크롤링"""
        try:
            await page.goto(self.naver_map_url, wait_until='domcontentloaded')
            await asyncio.sleep(2)
            
            search_query = f"{keyword} {name}"
            search_input_selector = '.input_search'
            await page.wait_for_selector(search_input_selector)
            await page.fill(search_input_selector, '')
            await asyncio.sleep(0.5)
            
            await page.fill(search_input_selector, search_query)
            await page.press(search_input_selector, 'Enter')
            await asyncio.sleep(3)
            
            await page.wait_for_selector('iframe#entryIframe', timeout=10000)
            entry_frame = page.frame_locator('iframe#entryIframe')
            await asyncio.sleep(3)
            
            extractor = StoreDetailExtractor(entry_frame, page)
            store_data = await extractor.extract_all_details()
            
            if store_data:
                actual_name = store_data[0]
                
                # 리소스 정리
                await OptimizedBrowserManager.clear_page_resources(page)
                
                return (store_data, actual_name)
            
            return None
            
        except TimeoutError:
            return None
        except Exception as e:
            self.logger.error(f"'{name}' 검색 중 오류: {e}")
            return None
    
    def _save_wrapper_with_total(self, batch_start: int, total: int):
        """저장 래퍼 팩토리 (total 포함)"""
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
                log_prefix="콘텐츠"
            )
        
        return wrapper
    
    async def _extract_item_name(self, item, idx: int, item_count: int) -> str:
        """아이템 이름 추출"""
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


async def main():
    """메인 함수"""
    logger = get_logger(__name__)
    
    logger.info("="*70)
    logger.info("🚀 네이버 지도 콘텐츠 크롤러 시작 (병렬 처리)")
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