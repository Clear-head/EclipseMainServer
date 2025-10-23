import json
import asyncio
from playwright.async_api import async_playwright, TimeoutError, Page
import sys, os
from dotenv import load_dotenv

load_dotenv(dotenv_path="src/.env")

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.logger.logger_handler import get_logger
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.search_strategy import NaverMapSearchStrategy
from src.service.crawl.utils.crawling_manager import CrawlingManager

logger = get_logger('crawling_bluer')


class BluerRestaurantCrawler:
    """Bluer 웹사이트 음식점 크롤링 클래스"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.bluer_url = "https://www.bluer.co.kr/search?query=&foodType=&foodTypeDetail=&feature=112&location=&locationDetail=&area=&areaDetail=&ribbonType=&priceRangeMin=0&priceRangeMax=1000&week=&hourMin=0&hourMax=48&year=&evaluate=&sort=&listType=card&isSearchName=false&isBrand=false&isAround=false&isMap=false&zone1=&zone2=&food1=&food2=&zone2Lat=&zone2Lng=&distance=1000&isMapList=false#restaurant-filter-bottom"
        self.data_saver = StoreDataSaver()
        self.search_strategy = NaverMapSearchStrategy()
        self.crawling_manager = CrawlingManager("Bluer")
        
        logger.info(f"✓ Bluer 크롤러 초기화 완료")
    
    async def crawl_all_pages(self, delay: int = 5, naver_delay: int = 20):
        """Bluer 전체 페이지 크롤링"""
        async with async_playwright() as p:
            # Bluer 크롤링용 브라우저
            bluer_browser = await p.chromium.launch(headless=self.headless)
            bluer_page = await bluer_browser.new_page()
            
            # 네이버 크롤링용 브라우저
            naver_browser = await p.chromium.launch(
                headless=self.headless,
                args=['--enable-features=ClipboardAPI']
            )
            naver_context = await naver_browser.new_context(
                permissions=['clipboard-read', 'clipboard-write']
            )
            naver_page = await naver_context.new_page()
            
            try:
                logger.info(f"Bluer 페이지 접속 중...")
                await bluer_page.goto(self.bluer_url, wait_until='networkidle')
                await asyncio.sleep(3)
                
                # 전체 음식점 목록 저장
                all_restaurants = []
                current_page = 1
                
                while True:
                    logger.info(f"=" * 60)
                    logger.info(f"📄 페이지 {current_page} 크롤링 시작")
                    logger.info(f"=" * 60)
                    
                    # 현재 페이지의 음식점 목록 추출
                    restaurants = await self._extract_restaurants_from_page(bluer_page)
                    
                    if restaurants:
                        logger.info(f"페이지 {current_page}에서 {len(restaurants)}개 음식점 발견")
                        all_restaurants.extend(restaurants)
                    else:
                        logger.warning(f"페이지 {current_page}에서 음식점을 찾지 못했습니다.")
                    
                    # 다음 페이지 버튼 확인 및 클릭
                    has_next = await self._click_next_page(bluer_page)
                    
                    if not has_next:
                        logger.info("=" * 60)
                        logger.info(f"✓ 마지막 페이지 도달! 총 {len(all_restaurants)}개 음식점 수집 완료")
                        logger.info("=" * 60)
                        break
                    
                    current_page += 1
                    await asyncio.sleep(delay)
                
                # 크롤링 매니저를 사용한 병렬 처리
                await self.crawling_manager.execute_crawling_with_save(
                    stores=all_restaurants,
                    crawl_func=lambda store, idx, total: self._crawl_single_store(naver_page, store),
                    save_func=self._save_wrapper,
                    delay=naver_delay
                )
                
            except Exception as e:
                logger.error(f"크롤링 중 오류 발생: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                await bluer_page.close()
                await bluer_browser.close()
                await naver_context.close()
                await naver_browser.close()
    
    async def _crawl_single_store(self, page: Page, store: tuple):
        """단일 매장 크롤링"""
        name, address = store
        
        # 검색 전략 사용
        async def extract_callback(entry_frame, page):
            extractor = StoreDetailExtractor(entry_frame, page)
            return await extractor.extract_all_details()
        
        return await self.search_strategy.search_with_multiple_strategies(
            page=page,
            store_name=name,
            road_address=address,
            extractor_callback=extract_callback
        )
    
    async def _save_wrapper(self, idx: int, total: int, store_data: tuple, store_name: str):
        """저장 래퍼"""
        return await self.data_saver.save_store_data(
            idx=idx,
            total=total,
            store_data=store_data,
            store_name=store_name,
            log_prefix="Bluer"
        )
    
    async def _extract_restaurants_from_page(self, page: Page):
        """현재 페이지에서 음식점 이름과 주소 추출"""
        restaurants = []
        
        try:
            await page.wait_for_selector('#list-restaurant', timeout=10000)
            await asyncio.sleep(2)
            
            list_items = await page.locator('#list-restaurant > li').all()
            logger.info(f"현재 페이지 리스트 아이템 수: {len(list_items)}")
            
            for idx, item in enumerate(list_items, 1):
                try:
                    # 음식점명 추출
                    name_selector = 'div > header > div.header-title > div:nth-child(2) > h3'
                    name_element = item.locator(name_selector)
                    
                    if await name_element.count() > 0:
                        name = await name_element.inner_text(timeout=3000)
                        name = name.strip()
                    else:
                        logger.warning(f"리스트 아이템 {idx}: 음식점명을 찾을 수 없습니다.")
                        continue
                    
                    # 주소 추출
                    address_selector = 'div > div > div.info > div:nth-child(1) > div'
                    address_element = item.locator(address_selector)
                    
                    if await address_element.count() > 0:
                        address = await address_element.inner_text(timeout=3000)
                        address = address.strip()
                    else:
                        logger.warning(f"리스트 아이템 {idx}: 주소를 찾을 수 없습니다.")
                        address = ""
                    
                    if name:
                        restaurants.append((name, address))
                        logger.info(f"  [{idx}] {name} - {address}")
                    
                except Exception as item_error:
                    logger.error(f"리스트 아이템 {idx} 추출 중 오류: {item_error}")
                    continue
            
        except TimeoutError:
            logger.error("리스트를 찾을 수 없습니다. (Timeout)")
        except Exception as e:
            logger.error(f"음식점 목록 추출 중 오류: {e}")
        
        return restaurants
    
    async def _click_next_page(self, page: Page) -> bool:
        """다음 페이지 버튼 클릭"""
        try:
            await page.wait_for_selector('#page-selection > ul', timeout=5000)
            await asyncio.sleep(1)
            
            page_items = await page.locator('#page-selection > ul > li').all()
            
            active_index = -1
            for idx, item in enumerate(page_items):
                class_attr = await item.get_attribute('class')
                if class_attr and 'active' in class_attr:
                    active_index = idx
                    break
            
            if active_index == -1:
                logger.warning("active 페이지를 찾을 수 없습니다.")
                return False
            
            next_index = active_index + 1
            if next_index >= len(page_items):
                logger.info("다음 페이지가 없습니다. (마지막 페이지)")
                return False
            
            next_button = page_items[next_index]
            await next_button.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            
            clickable = next_button.locator('a, button').first
            if await clickable.count() > 0:
                await clickable.click()
            else:
                await next_button.click()
            
            logger.info(f"✓ 다음 페이지로 이동 중...")
            await asyncio.sleep(2)
            
            return True
            
        except TimeoutError:
            logger.error("페이지 선택 영역을 찾을 수 없습니다.")
            return False
        except Exception as e:
            logger.error(f"다음 페이지 클릭 중 오류: {e}")
            return False


async def main():
    """메인 함수"""
    headless_mode = False
    page_delay = 5
    naver_delay = 30
    
    logger.info("=" * 80)
    logger.info("Bluer 음식점 크롤링 시작")
    logger.info("=" * 80)
    
    try:
        crawler = BluerRestaurantCrawler(headless=headless_mode)
        await crawler.crawl_all_pages(delay=page_delay, naver_delay=naver_delay)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ 모든 크롤링 완료!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())