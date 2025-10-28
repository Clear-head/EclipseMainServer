import json
import asyncio
from playwright.async_api import async_playwright, TimeoutError, Page
import re
from typing import Optional, List, Tuple
import sys, os
import datetime
import aiohttp
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(dotenv_path="src/.env")

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.logger.custom_logger import get_logger

# 외부 API 서비스 import
from src.infra.external.kakao_geocoding_service import GeocodingService
from src.infra.external.category_classifier_service import CategoryTypeClassifier

# 유틸리티 import
from src.service.crawl.utils.address_parser import AddressParser
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.crawling_manager import CrawlingManager  # 추가

class NaverMapFavoriteCrawler:
    """네이버 지도 즐겨찾기 목록 크롤링을 위한 클래스"""
    
    def __init__(self, headless: bool = False):
        self.logger = get_logger(__name__)
        self.headless = headless
        self.geocoding_service = GeocodingService()
        self.category_classifier = CategoryTypeClassifier()
        self.data_saver = StoreDataSaver()
        self.crawling_manager = CrawlingManager("즐겨찾기")  # 추가
        
    async def _save_store_data(self, idx: int, total: int, store_data: Tuple, place_name: str):
        """공통 저장 로직 호출"""
        return await self.data_saver.save_store_data(
            idx=idx,
            total=total,
            store_data=store_data,
            store_name=place_name,
            log_prefix="즐겨찾기"
        )
        
    async def crawl_favorite_list(self, favorite_url: str, delay: int = 20, output_file: str = None):
        """
        네이버 지도 즐겨찾기 목록에서 장소들을 크롤링
        크롤링과 저장을 분리하여 병렬 처리
        
        Args:
            favorite_url: 즐겨찾기 URL
            delay: 각 장소 크롤링 사이의 대기 시간(초)
            output_file: 결과 저장 파일 (선택)
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--enable-features=ClipboardAPI']
            )
            
            context = await browser.new_context(
                permissions=['clipboard-read', 'clipboard-write']
            )
            page = await context.new_page()
            
            try:
                # 즐겨찾기 페이지로 이동
                await page.goto(favorite_url, wait_until='domcontentloaded', timeout=60000)
                await asyncio.sleep(10)
                
                # myPlaceBookmarkListIframe 대기
                try:
                    await page.wait_for_selector('iframe#myPlaceBookmarkListIframe', timeout=30000)
                except Exception as e:
                    self.logger.error(f"iframe을 찾을 수 없습니다: {e}")
                    html = await page.content()
                    with open('debug_main_page.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    return
                
                # iframe 가져오기
                list_frame_locator = page.frame_locator('iframe#myPlaceBookmarkListIframe')
                list_frame = page.frame('myPlaceBookmarkListIframe')
                
                if not list_frame:
                    self.logger.error("myPlaceBookmarkListIframe을 찾을 수 없습니다.")
                    return
                
                await asyncio.sleep(3)
                
                # 장소 선택자 찾기
                place_selector = await self._find_place_selector(list_frame_locator, list_frame)
                if not place_selector:
                    return
                
                # 스크롤하여 모든 장소 로드
                await self._scroll_to_load_all_places(list_frame_locator, place_selector)
                
                # 최종 장소 개수 확인
                places = await list_frame_locator.locator(place_selector).all()
                total = len(places)
                
                if total == 0:
                    self.logger.warning("크롤링할 장소가 없습니다.")
                    return
                
                # 장소 정보를 리스트로 변환 (인덱스와 함께)
                place_indices = list(range(total))
                
                # CrawlingManager를 사용한 병렬 처리
                await self.crawling_manager.execute_crawling_with_save(
                    stores=place_indices,
                    crawl_func=lambda idx, i, t: self._crawl_single_place(
                        page, list_frame_locator, place_selector, idx, t
                    ),
                    save_func=self._save_wrapper,
                    delay=delay
                )
                
            except Exception as e:
                self.logger.error(f"즐겨찾기 크롤링 중 오류: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                await context.close()
                await browser.close()
    
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
                    # logger.info(f"선택자 발견: {selector} - {len(elements)}개 요소")
                    return selector
            except Exception as e:
                self.logger.debug(f"선택자 없음: {selector} - {e}")
                continue
        
        # 선택자를 찾지 못한 경우
        html_content = await list_frame.content()
        with open('debug_iframe.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        self.logger.error("장소 목록 선택자를 찾을 수 없습니다. debug_iframe.html 파일을 확인하세요.")
        return None
    
    async def _crawl_single_place(
        self, 
        page: Page, 
        list_frame_locator, 
        place_selector: str, 
        idx: int, 
        total: int
    ):
        """
        단일 장소 크롤링
        
        Args:
            page: 메인 페이지
            list_frame_locator: 리스트 iframe locator
            place_selector: 장소 선택자
            idx: 장소 인덱스 (0부터 시작)
            total: 전체 장소 수
        
        Returns:
            Tuple: (store_data, place_name) 또는 None
        """
        try:
            # 매번 목록을 다시 가져와야 함 (DOM이 변경되기 때문)
            places = await list_frame_locator.locator(place_selector).all()
            
            if idx >= len(places):
                self.logger.error(f"장소 인덱스가 범위를 벗어났습니다: {idx}/{len(places)}")
                return None
            
            place = places[idx]
            
            # 장소명 미리 가져오기 (로깅용)
            place_name = await self._extract_place_name(place, idx)
            
            # 장소 클릭
            await self._click_place(place)
            await asyncio.sleep(3)
            
            # 폐업 팝업 체크
            if await self._check_and_close_popup(list_frame_locator, place_name):
                self.logger.warning(f"'{place_name}' 폐업 또는 접근 불가")
                return None
            
            # entry iframe 가져오기 (메인 페이지에서)
            entry_frame = await self._get_entry_frame(page)
            
            if not entry_frame:
                self.logger.error(f"entry iframe을 찾을 수 없습니다.")
                return None
            
            # 상세 정보 추출
            extractor = StoreDetailExtractor(entry_frame, page)
            store_data = await extractor.extract_all_details()
            
            if store_data:
                return (store_data, place_name)
            else:
                self.logger.error(f"상점 정보 추출 실패: {place_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"크롤링 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    async def _extract_place_name(self, place, idx: int) -> str:
        """장소명 추출"""
        try:
            name_selectors = [
                'div.name', 
                'span.name', 
                '.place_name', 
                'a.name', 
                '.item_name', 
                'span'
            ]
            
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
    
    async def _click_place(self, place):
        """장소 클릭"""
        try:
            clickable = place.locator('div, li[role="button"]').first
            await clickable.click(timeout=5000)
        except:
            await place.click(timeout=5000)
    
    async def _check_and_close_popup(self, list_frame_locator, place_name: str) -> bool:
        """
        폐업 팝업 체크 및 닫기
        
        Returns:
            bool: 팝업이 있었으면 True, 없으면 False
        """
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
                    self.logger.warning(f"'{place_name}' 폐업 팝업 감지! (셀렉터: {popup_selector})")
                    is_popup_found = True
                    break
            except Exception as e:
                self.logger.debug(f"셀렉터 '{popup_selector}' 실패: {e}")
                continue
        
        if is_popup_found:
            # 확인 버튼 클릭
            button_selectors = [
                'body > div:nth-child(4) > div > div._popup_62e0u_1._at_pc_62e0u_21._show_62e0u_8 > div._popup_buttons_62e0u_85 > button'
            ]
            
            button_clicked = False
            for button_selector in button_selectors:
                try:
                    popup_button = list_frame_locator.locator(button_selector).first
                    if await popup_button.is_visible(timeout=1000):
                        await popup_button.click(timeout=2000)
                        await asyncio.sleep(0.5)
                        button_clicked = True
                        break
                except Exception as e:
                    self.logger.debug(f"버튼 셀렉터 '{button_selector}' 실패: {e}")
                    continue
            
            if not button_clicked:
                self.logger.error("팝업 닫기 버튼을 찾을 수 없습니다")
        
        return is_popup_found
    
    async def _save_wrapper(self, idx: int, total: int, store_data_tuple, place_name: str):
        """
        저장 래퍼 함수
        
        Args:
            store_data_tuple: (store_data, place_name) 튜플
        """
        if store_data_tuple is None:
            return (False, "크롤링 실패")
        
        store_data, actual_place_name = store_data_tuple
        
        return await self.data_saver.save_store_data(
            idx=idx,
            total=total,
            store_data=store_data,
            store_name=actual_place_name,
            log_prefix="즐겨찾기"
        )
    
    async def _scroll_to_load_all_places(self, frame_locator, place_selector: str):
        """
        iframe 내부를 스크롤하여 모든 장소를 로드
        
        Args:
            frame_locator: iframe locator
            place_selector: 장소 선택자
        """
        # logger.info("스크롤 시작...")
        
        scroll_container_selectors = [
            '#app > div > div:nth-child(3)',
            '#app > div > div:nth-child(3) > div',
            'div[class*="scroll"]',
            'div[style*="overflow"]',
        ]
        
        prev_count = 0
        same_count = 0
        max_same_count = 3
        
        for scroll_attempt in range(500):
            try:
                # 현재 장소 개수
                places = await frame_locator.locator(place_selector).all()
                current_count = len(places)
                
                # if scroll_attempt % 10 == 0:  # 10회마다 로그
                #     logger.info(f"스크롤 {scroll_attempt + 1}회: {current_count}개 장소 발견")
                
                # 개수가 같으면 카운트 증가
                if current_count == prev_count:
                    same_count += 1
                    if same_count >= max_same_count:
                        # logger.info(f"스크롤 완료: 총 {current_count}개 장소")
                        break
                else:
                    same_count = 0
                
                prev_count = current_count
                
                # 마지막 요소로 스크롤
                if current_count > 0:
                    last_place = frame_locator.locator(place_selector).nth(current_count - 1)
                    try:
                        await last_place.scroll_into_view_if_needed(timeout=3000)
                    except:
                        pass
                
                # 스크롤 컨테이너에서 직접 스크롤 시도
                for container_selector in scroll_container_selectors:
                    try:
                        await frame_locator.locator(container_selector).evaluate(
                            'element => element.scrollTop = element.scrollHeight'
                        )
                        break
                    except:
                        continue
                
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.warning(f"스크롤 중 오류: {e}")
                break
        
        # logger.info("스크롤 완료")
    
    async def _get_entry_frame(self, page: Page):
        """상세 정보 iframe 가져오기"""
        try:
            await page.wait_for_selector('iframe#entryIframe', timeout=10000)
            entry_frame = page.frame_locator('iframe#entryIframe')
            await asyncio.sleep(3)
            return entry_frame
        except TimeoutError:
            self.logger.error("entryIframe을 찾을 수 없습니다.")
            return None


async def main(favorite_url = 'https://map.naver.com/p/favorite/sSjt-6mGnGEqi8HA:2D_MP7QkdZtDuASbcBgfEqXAYqV5Tw/folder/723cd582cd1e43dcac5234ad055c7494/pc/place/1477750254?c=10.15,0,0,0,dh&placePath=/home?from=map&fromPanelNum=2&timestamp=202510210943&locale=ko&svcName=map_pcv5'):
    """메인 함수"""
    logger = get_logger(__name__)
    # 크롤러 생성
    crawler = NaverMapFavoriteCrawler(headless=False)
    
    # 즐겨찾기 목록 크롤링
    await crawler.crawl_favorite_list(
        favorite_url=favorite_url,
        delay=10,
        output_file=None
    )