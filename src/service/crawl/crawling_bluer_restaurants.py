import json
import asyncio
from playwright.async_api import async_playwright, TimeoutError, Page
import re
from typing import Optional, List, Tuple
import sys, os
import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(dotenv_path="src/.env")

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.logger.logger_handler import get_logger
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver

# 로거 초기화
logger = get_logger('crawling_bluer')

class BluerRestaurantCrawler:
    """Bluer 웹사이트 음식점 크롤링 클래스"""
    
    def __init__(self, headless: bool = False):
        """
        Args:
            headless: 헤드리스 모드 사용 여부
        """
        self.headless = headless
        self.bluer_url = "https://www.bluer.co.kr/search?query=&foodType=&foodTypeDetail=&feature=112&location=&locationDetail=&area=&areaDetail=&ribbonType=&priceRangeMin=0&priceRangeMax=1000&week=&hourMin=0&hourMax=48&year=&evaluate=&sort=&listType=card&isSearchName=false&isBrand=false&isAround=false&isMap=false&zone1=&zone2=&food1=&food2=&zone2Lat=&zone2Lng=&distance=1000&isMapList=false#restaurant-filter-bottom"
        self.naver_map_url = "https://map.naver.com/v5/search"
        self.data_saver = StoreDataSaver()
        
        logger.info(f"✓ Bluer 크롤러 초기화 완료")
    
    async def crawl_all_pages(self, delay: int = 5, naver_delay: int = 20):
        """
        Bluer 전체 페이지 크롤링
        
        Args:
            delay: Bluer 페이지 간 딜레이 (초)
            naver_delay: 네이버 크롤링 간 딜레이 (초)
        """
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
                # Bluer 페이지로 이동
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
                
                # 네이버 지도에서 상세 정보 크롤링 및 저장
                await self._crawl_naver_details(naver_page, all_restaurants, naver_delay)
                
            except Exception as e:
                logger.error(f"크롤링 중 오류 발생: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                await bluer_page.close()
                await bluer_browser.close()
                await naver_context.close()
                await naver_browser.close()
    
    async def _extract_restaurants_from_page(self, page: Page) -> List[Tuple[str, str]]:
        """
        현재 페이지에서 음식점 이름과 주소 추출
        
        Returns:
            List[Tuple[str, str]]: [(음식점명, 주소), ...]
        """
        restaurants = []
        
        try:
            # 리스트 컨테이너가 로드될 때까지 대기
            await page.wait_for_selector('#list-restaurant', timeout=10000)
            await asyncio.sleep(2)
            
            # 리스트 아이템 개수 확인
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
        """
        다음 페이지 버튼 클릭
        
        Returns:
            bool: 다음 페이지가 있으면 True, 없으면 False
        """
        try:
            # 페이지 선택 영역 대기
            await page.wait_for_selector('#page-selection > ul', timeout=5000)
            await asyncio.sleep(1)
            
            # active 클래스를 가진 현재 페이지 찾기
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
            
            # 다음 버튼이 있는지 확인
            next_index = active_index + 1
            if next_index >= len(page_items):
                logger.info("다음 페이지가 없습니다. (마지막 페이지)")
                return False
            
            # 다음 버튼 클릭
            next_button = page_items[next_index]
            await next_button.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            
            # 버튼 안의 a 태그 또는 버튼 자체 클릭
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
    
    async def _crawl_naver_details(self, naver_page: Page, restaurants: List[Tuple[str, str]], delay: int):
        """
        네이버 지도에서 음식점 상세 정보 크롤링 및 저장
        
        Args:
            naver_page: 네이버 크롤링용 페이지
            restaurants: [(음식점명, 주소), ...]
            delay: 크롤링 간 딜레이 (초)
        """
        total = len(restaurants)
        success_count = 0
        fail_count = 0
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"🗺️  네이버 지도 상세 정보 크롤링 시작 (총 {total}개)")
        logger.info("=" * 60)
        
        save_tasks = []
        
        for idx, (name, address) in enumerate(restaurants, 1):
            logger.info(f"[네이버 크롤링 {idx}/{total}] '{name}' 크롤링 진행 중...")
            logger.info(f"  - 주소: {address}")
            
            # 네이버 지도에서 검색
            store_data = await self._search_naver_map(naver_page, name, address)
            
            if store_data:
                logger.info(f"[네이버 크롤링 {idx}/{total}] '{name}' 크롤링 완료")
                
                # 저장 태스크 생성 (백그라운드에서 실행)
                save_task = asyncio.create_task(
                    self.data_saver.save_store_data(
                        idx=idx,
                        total=total,
                        store_data=store_data,
                        store_name=name,
                        log_prefix="Bluer"
                    )
                )
                save_tasks.append(save_task)
                
                # 마지막 상점이 아니면 딜레이
                if idx < total:
                    await asyncio.sleep(delay)
            else:
                fail_count += 1
                logger.error(f"[네이버 크롤링 {idx}/{total}] '{name}' 크롤링 실패")
                
                # 실패해도 딜레이
                if idx < total:
                    await asyncio.sleep(delay)
        
        # 모든 크롤링이 끝난 후 저장 태스크들이 완료될 때까지 대기
        logger.info("=" * 60)
        logger.info(f"모든 크롤링 완료! 저장 작업 완료 대기 중... ({len(save_tasks)}개)")
        logger.info("=" * 60)
        
        if save_tasks:
            save_results = await asyncio.gather(*save_tasks, return_exceptions=True)
            
            # 저장 결과 집계
            for result in save_results:
                if isinstance(result, Exception):
                    fail_count += 1
                elif isinstance(result, tuple):
                    success, msg = result
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
        
        logger.info("=" * 60)
        logger.info(f"전체 작업 완료: 성공 {success_count}/{total}, 실패 {fail_count}/{total}")
        logger.info("=" * 60)
    
    def _extract_road_name(self, address: str) -> str:
        """
        주소에서 도로명(~로, ~길)까지만 추출
        
        Args:
            address: 전체 주소
            
        Returns:
            str: ~로 또는 ~길까지의 주소
        """
        if not address:
            return ""
        
        address_parts = address.split()
        result_parts = []
        
        for part in address_parts:
            result_parts.append(part)
            
            # ~로, ~길이 나오면 바로 종료
            if part.endswith('로') or part.endswith('길'):
                break
            
            # 안전장치: 최대 5개 요소까지
            if len(result_parts) >= 5:
                break
        
        return " ".join(result_parts)
    
    async def _search_naver_map(self, page: Page, store_name: str, store_address: str):
        """
        네이버 지도에서 검색 및 정보 추출
        
        Args:
            page: Playwright Page 객체
            store_name: 음식점명
            store_address: 주소
            
        Returns:
            Tuple or None: (name, address, phone, hours, image, sub_category, tags)
        """
        # 1차 시도: ~로/~길 + 매장명
        if store_address:
            road_name = self._extract_road_name(store_address)
            if road_name:
                first_keyword = f"{road_name} {store_name}"
                logger.info(f"  1차 검색: {first_keyword}")
                result = await self._search_single(page, first_keyword)
                if result:
                    return result
                await asyncio.sleep(4)
                logger.warning(f"  1차 검색 실패")
        
        # 2차 시도: 전체 주소 + 매장명
        if store_address:
            second_keyword = f"{store_address} {store_name}"
            logger.info(f"  2차 검색: {second_keyword}")
            result = await self._search_single(page, second_keyword)
            if result:
                return result
            await asyncio.sleep(4)
            logger.warning(f"  2차 검색 실패")
        
        # 3차 시도: 매장명만
        logger.info(f"  3차 검색: {store_name}")
        result = await self._search_single(page, store_name)
        if result:
            return result
        await asyncio.sleep(4)
        logger.warning(f"  3차 검색 실패")
        
        # 4차 시도: 주소만
        if store_address:
            logger.info(f"  4차 검색: {store_address}")
            result = await self._search_single(page, store_address)
            if result:
                return result
            await asyncio.sleep(4)
            logger.warning(f"  4차 검색 실패")
        
        logger.error(f"  모든 검색 시도 실패: {store_name}")
        return None
    
    async def _search_single(self, page: Page, keyword: str):
        """단일 키워드로 검색"""
        try:
            # 네이버 지도 이동
            await page.goto(self.naver_map_url)
            
            # 검색
            search_input_selector = '.input_search'
            await page.wait_for_selector(search_input_selector)
            await asyncio.sleep(1)
            
            await page.fill(search_input_selector, '')
            await asyncio.sleep(0.5)
            
            await page.fill(search_input_selector, keyword)
            await page.press(search_input_selector, 'Enter')
            
            # entry iframe 대기
            await page.wait_for_selector('iframe#entryIframe', timeout=10000)
            entry_frame = page.frame_locator('iframe#entryIframe')
            await asyncio.sleep(3)
            
            # 정보 추출
            extractor = StoreDetailExtractor(entry_frame, page)
            return await extractor.extract_all_details()
            
        except TimeoutError:
            logger.error(f"'{keyword}' 검색 결과를 찾을 수 없습니다.")
            return None
        except Exception as e:
            logger.error(f"'{keyword}' 검색 중 오류: {e}")
            return None


async def main():
    """메인 함수"""
    
    # ========================================
    # 크롤링 설정
    # ========================================
    headless_mode = False   # True로 설정하면 브라우저가 보이지 않음
    page_delay = 5          # Bluer 페이지 간 대기 시간 (초)
    naver_delay = 30        # 네이버 크롤링 간 대기 시간 (초)
    
    # ========================================
    # 크롤링 실행
    # ========================================
    
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