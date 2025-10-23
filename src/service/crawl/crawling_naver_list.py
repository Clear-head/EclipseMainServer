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
from src.logger.logger_handler import get_logger
from src.domain.dto.insert_category_dto import InsertCategoryDto
from src.domain.dto.insert_category_tags_dto import InsertCategoryTagsDTO
from src.service.crawl.insert_crawled import insert_category, insert_category_tags, insert_tags
from src.service.crawl.update_crawled import update_category, update_category_tags
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.service.crawl.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.store_data_saver import StoreDataSaver

# 외부 API 서비스 import
from src.infra.external.kakao_geocoding_service import GeocodingService
from src.infra.external.category_classifier_service import CategoryTypeClassifier

# 유틸리티 import
from src.service.crawl.utils.address_parser import AddressParser

# 로거 초기화
logger = get_logger('crawling_naver')

class NaverMapFavoriteCrawler:
    """네이버 지도 즐겨찾기 목록 크롤링을 위한 클래스"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.geocoding_service = GeocodingService()
        self.category_classifier = CategoryTypeClassifier()
        
        self.data_saver = StoreDataSaver()
        
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
                args=['--enable-features=ClipboardAPI']  # 클립보드 API 활성화
            )
            
            # 컨텍스트 생성 시 클립보드 권한 부여
            context = await browser.new_context(
                permissions=['clipboard-read', 'clipboard-write']
            )
            page = await context.new_page()
            
            try:
                # 즐겨찾기 페이지로 이동
                # logger.info(f"즐겨찾기 페이지로 이동: {favorite_url}")
                await page.goto(favorite_url, wait_until='domcontentloaded', timeout=60000)
                # logger.info("페이지 로딩 대기 중...")
                await asyncio.sleep(10)
                
                # myPlaceBookmarkListIframe 대기
                # logger.info("myPlaceBookmarkListIframe 대기 중...")
                try:
                    await page.wait_for_selector('iframe#myPlaceBookmarkListIframe', timeout=30000)
                except Exception as e:
                    logger.error(f"iframe을 찾을 수 없습니다: {e}")
                    html = await page.content()
                    with open('debug_main_page.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    # logger.info("debug_main_page.html 파일에 페이지 내용을 저장했습니다.")
                    return
                
                # iframe 가져오기
                list_frame_locator = page.frame_locator('iframe#myPlaceBookmarkListIframe')
                list_frame = page.frame('myPlaceBookmarkListIframe')
                
                if not list_frame:
                    logger.error("myPlaceBookmarkListIframe을 찾을 수 없습니다.")
                    return
                
                # logger.info("myPlaceBookmarkListIframe 발견")
                await asyncio.sleep(3)
                
                # 여러 가능한 선택자 시도
                possible_selectors = [
                    '#app > div > div:nth-child(3) > div > ul > li',
                    'ul.list_place > li',
                    'ul > li',
                    '[role="list"] > *',
                ]
                
                place_selector = None
                
                # iframe 내부에서 선택자 찾기
                for selector in possible_selectors:
                    try:
                        # logger.info(f"선택자 시도: {selector}")
                        elements = await list_frame_locator.locator(selector).all()
                        if len(elements) > 0:
                            place_selector = selector
                            # logger.info(f"선택자 발견: {selector} - {len(elements)}개 요소")
                            break
                    except Exception as e:
                        logger.warning(f"선택자 없음: {selector} - {e}")
                        continue
                
                if not place_selector:
                    html_content = await list_frame.content()
                    with open('debug_iframe.html', 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.error("장소 목록 선택자를 찾을 수 없습니다. debug_iframe.html 파일을 확인하세요.")
                    return
                
                # 스크롤하여 모든 장소 로드
                # logger.info("스크롤하여 모든 장소 로드 중...")
                await self._scroll_to_load_all_places(list_frame_locator, place_selector)
                
                # 최종 장소 개수 확인
                places = await list_frame_locator.locator(place_selector).all()
                total = len(places)
                
                if total == 0:
                    logger.warning("크롤링할 장소가 없습니다.")
                    return
                
                # logger.info(f"총 {total}개 장소 크롤링 시작")
                # logger.info("=" * 60)
                
                success_count = 0
                fail_count = 0
                
                # 저장 태스크를 담을 리스트
                save_tasks = []
                
                # 각 장소 크롤링
                for idx in range(total):
                    try:
                        # 매번 목록을 다시 가져와야 함 (DOM이 변경되기 때문)
                        places = await list_frame_locator.locator(place_selector).all()
                        
                        if idx >= len(places):
                            logger.error(f"[크롤링 {idx+1}/{total}] 장소 인덱스가 범위를 벗어났습니다.")
                            fail_count += 1
                            continue
                        
                        place = places[idx]
                        
                        # 장소명 미리 가져오기 (로깅용)
                        try:
                            name_selectors = ['div.name', 'span.name', '.place_name', 'a.name', '.item_name', 'span']
                            place_name = None
                            
                            for name_sel in name_selectors:
                                try:
                                    place_name = await place.locator(name_sel).first.inner_text(timeout=2000)
                                    if place_name and place_name.strip():
                                        break
                                except:
                                    continue
                            
                            if not place_name:
                                place_name = f"장소 {idx+1}"
                        except:
                            place_name = f"장소 {idx+1}"
                        
                        # 장소 클릭
                        logger.info(f"[크롤링 {idx+1}/{total}] '{place_name}' 시작 중...")

                        # 클릭 가능한 요소 찾기
                        try:
                            clickable = place.locator('div, li[role="button"]').first
                            await clickable.click(timeout=5000)
                        except:
                            await place.click(timeout=5000)

                        await asyncio.sleep(3)

                        # 폐업 팝업 체크
                        # logger.info(f"[크롤링 {idx+1}/{total}] 폐업 팝업 체크 중...")

                        popup_selectors = [
                            'body > div:nth-child(4) > div._show_62e0u_8',
                            'div._show_62e0u_8',
                            'div._popup_62e0u_1._show_62e0u_8',
                            'div[class*="_show_"]',
                            'div._popup_62e0u_1',
                        ]

                        is_popup_found = False
                        popup_element = None

                        for popup_selector in popup_selectors:
                            try:
                                popup_element = list_frame_locator.locator(popup_selector).first
                                is_visible = await popup_element.is_visible(timeout=1000)
                                
                                if is_visible:
                                    logger.warning(f"[크롤링 {idx+1}/{total}] '{place_name}' 폐업 팝업 감지! (셀렉터: {popup_selector})")
                                    is_popup_found = True
                                    break
                            except Exception as e:
                                logger.debug(f"셀렉터 '{popup_selector}' 실패: {e}")
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
                                        # logger.info(f"폐업 팝업 닫기 완료 (버튼 셀렉터: {button_selector})")
                                        button_clicked = True
                                        break
                                except Exception as e:
                                    logger.debug(f"버튼 셀렉터 '{button_selector}' 실패: {e}")
                                    continue
                            
                            if not button_clicked:
                                logger.error("팝업 닫기 버튼을 찾을 수 없습니다")
                            
                            fail_count += 1
                            
                            # 마지막 장소가 아니면 딜레이
                            if idx < total - 1:
                                # logger.info(f"[대기] {delay}초 대기 중...")
                                await asyncio.sleep(delay)
                            
                            continue  # 다음 장소로 건너뛰기

                        # logger.info(f"[크롤링 {idx+1}/{total}] 팝업 없음 - 정상 크롤링 진행")

                        # entry iframe 가져오기 (메인 페이지에서)
                        entry_frame = await self._get_entry_frame(page)

                        if not entry_frame:
                            logger.error(f"[크롤링 {idx+1}/{total}] entry iframe을 찾을 수 없습니다.")
                            fail_count += 1
                            continue

                        # 상세 정보 추출
                        extractor = StoreDetailExtractor(entry_frame, page)
                        store_data = await extractor.extract_all_details()
                        
                        if store_data:
                            logger.info(f"[크롤링 {idx+1}/{total}] '{place_name}' 크롤링 완료")
                            
                            # 저장 태스크 생성 (백그라운드에서 실행)
                            save_task = asyncio.create_task(
                                self._save_store_data(idx + 1, total, store_data, place_name)
                            )
                            save_tasks.append(save_task)
                            
                            # 크롤링 완료 후 바로 delay 시작
                            if idx < total - 1:
                                # logger.info(f"[대기] {delay}초 대기 중... (저장은 백그라운드에서 진행)")
                                await asyncio.sleep(delay)
                            
                        else:
                            fail_count += 1
                            logger.error(f"[크롤링 {idx+1}/{total}] 상점 정보 추출 실패")
                            
                            # 실패해도 딜레이
                            if idx < total - 1:
                                # logger.info(f"[대기] {delay}초 대기 중...")
                                await asyncio.sleep(delay)
                        
                    except Exception as e:
                        fail_count += 1
                        logger.error(f"[크롤링 {idx+1}/{total}] 크롤링 중 오류: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        
                        # 오류가 발생해도 딜레이
                        if idx < total - 1:
                            # logger.info(f"[대기] {delay}초 대기 중...")
                            await asyncio.sleep(delay)
                        continue
                
                # 모든 크롤링이 끝난 후 저장 태스크들이 완료될 때까지 대기
                # logger.info("=" * 60)
                logger.info(f"모든 크롤링 완료! 저장 작업 완료 대기 중... ({len(save_tasks)}개)")
                # logger.info("=" * 60)
                
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
                
                # logger.info("=" * 60)
                logger.info(f"전체 작업 완료: 성공 {success_count}/{total}, 실패 {fail_count}/{total}")
                # logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"즐겨찾기 크롤링 중 오류: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                await context.close()
                await browser.close()
    
    async def _scroll_to_load_all_places(self, frame_locator, place_selector: str):
        """
        iframe 내부를 스크롤하여 모든 장소를 로드
        
        Args:
            frame_locator: iframe locator
            place_selector: 장소 선택자
        """
        # logger.info("스크롤 시작...")
        
        # 스크롤 컨테이너 찾기 (여러 가능한 선택자 시도)
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
                
                # logger.info(f"스크롤 {scroll_attempt + 1}회: {current_count}개 장소 발견")
                
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
                logger.warning(f"스크롤 중 오류: {e}")
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
            logger.error("entryIframe을 찾을 수 없습니다.")
            return None


async def main(favorite_url = 'https://map.naver.com/p/favorite/sSjt-6mGnGEqi8HA:2D_MP7QkdZtDuASbcBgfEqXAYqV5Tw/folder/723cd582cd1e43dcac5234ad055c7494/pc/place/1477750254?c=10.15,0,0,0,dh&placePath=/home?from=map&fromPanelNum=2&timestamp=202510210943&locale=ko&svcName=map_pcv5'):
    """메인 함수"""
    
    # 크롤러 생성
    crawler = NaverMapFavoriteCrawler(headless=False)
    
    # 즐겨찾기 목록 크롤링
    await crawler.crawl_favorite_list(
        favorite_url=favorite_url,
        delay=30,
        output_file=None
    )

if __name__ == "__main__":
    asyncio.run(main("https://map.naver.com/p/favorite/sharedPlace/folder/a5b889b0ec9d4bafa6156d25cde3fedd/pc?c=6.00,0,0,0,dh"))