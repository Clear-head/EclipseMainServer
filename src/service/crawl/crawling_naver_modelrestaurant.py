import json
import asyncio
from playwright.async_api import async_playwright, TimeoutError, Page
import re
from typing import Optional, List, Tuple
import sys, os
import datetime
import aiohttp
from dotenv import load_dotenv
import xml.etree.ElementTree as ET

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
from src.infra.external.seoul_district_api_service import SeoulDistrictAPIService
from src.infra.external.kakao_geocoding_service import GeocodingService
from src.infra.external.category_classifier_service import CategoryTypeClassifier

# 유틸리티 import
from src.service.crawl.utils.address_parser import AddressParser

# 로거 초기화
logger = get_logger('crawling_naver_model')

class NaverMapDistrictCrawler:
    """서울시 각 구 API 데이터 크롤링 클래스"""
    
    def __init__(self, district_name: str, headless: bool = False):
        """
        Args:
            district_name: 크롤링할 구 이름 (예: '강남구', '서초구')
            headless: 헤드리스 모드 사용 여부
        """
        self.district_name = district_name
        self.headless = headless
        self.naver_map_url = "https://map.naver.com/v5/search"
        self.geocoding_service = GeocodingService()
        self.category_classifier = CategoryTypeClassifier()
        
        self.data_saver = StoreDataSaver()
        
        # logger.info(f"✓ {district_name} 크롤러 초기화 완료")
    
    async def _save_store_data(self, idx: int, total: int, store_data: Tuple, store_name: str, store_id: int, api_sub_category: str):
        """공통 저장 로직 호출"""
        return await self.data_saver.save_store_data(
            idx=idx,
            total=total,
            store_data=store_data,
            store_name=store_name,
            log_prefix=self.district_name
        )
    
    async def crawl_district_api(self, delay: int = 20):
        """
        해당 구의 API에서 데이터를 가져와 크롤링
        크롤링과 저장을 분리하여 병렬 처리
        
        Args:
            delay: 크롤링 간 딜레이 (초)
        """
        # 해당 구의 API에서 데이터 가져오기 (비동기)
        api_service = SeoulDistrictAPIService(self.district_name)
        api_data = await api_service.fetch_all_restaurants()
        
        if not api_data:
            logger.warning(f"{self.district_name} API에서 데이터를 가져올 수 없습니다.")
            return
        
        # 크롤링용 포맷으로 변환
        stores = api_service.convert_to_store_format(api_data)
        
        total = len(stores)
        success_count = 0
        fail_count = 0
        
        logger.info(f"총 {total}개 {self.district_name} 모범음식점 크롤링 시작")
        # logger.info("=" * 60)
        
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
                # 저장 태스크를 담을 리스트
                save_tasks = []
                
                for idx, store in enumerate(stores, 1):
                    store_id = store['id']
                    store_name = store['name']
                    store_address = store['address']  # 지번 주소
                    road_address = store['road_address']  # 도로명 주소 (SITE_ADDR_RD)
                    api_sub_category = store['sub_category']  # API 서브 카테고리
                    admdng_nm = store['admdng_nm']
                    
                    logger.info(f"[{self.district_name} 크롤링 {idx}/{total}] ID {store_id}: '{store_name}' (행정동: {admdng_nm}) 크롤링 진행 중...")
                    # logger.info(f"  - API 서브 카테고리: {api_sub_category}")
                    # logger.info(f"  - 지번 주소: {store_address}")
                    # logger.info(f"  - 도로명 주소: {road_address}")
                    
                    # 네이버 지도에서 검색 (도로명 주소 전달)
                    store_data = await self._search_and_extract(page, store_name, store_address, road_address)
                    
                    if store_data:
                        # store_data에서 네이버 서브 카테고리 추출
                        naver_sub_category = store_data[5]  # (name, address, phone, hours, image, sub_category, tags)
                        # logger.info(f"  - 네이버 서브 카테고리: {naver_sub_category}")
                        logger.info(f"[{self.district_name} 크롤링 {idx}/{total}] ID {store_id} '{store_name}' 크롤링 완료")
                        
                        # 저장 태스크 생성 (백그라운드에서 실행)
                        save_task = asyncio.create_task(
                            self._save_store_data(idx, total, store_data, store_name, store_id, api_sub_category)
                        )
                        save_tasks.append(save_task)
                        
                        # 마지막 상점이 아니면 딜레이
                        if idx < total:
                            # logger.info(f"[{self.district_name} 대기] {delay}초 대기 중... (저장은 백그라운드에서 진행)")
                            await asyncio.sleep(delay)
                    else:
                        fail_count += 1
                        logger.error(f"[{self.district_name} 크롤링 {idx}/{total}] ID {store_id} '{store_name}' 크롤링 실패")
                        
                        # 실패해도 딜레이
                        if idx < total:
                            # logger.info(f"[{self.district_name} 대기] {delay}초 대기 중...")
                            await asyncio.sleep(delay)
                
                # 모든 크롤링이 끝난 후 저장 태스크들이 완료될 때까지 대기
                # logger.info("=" * 60)
                logger.info(f"{self.district_name} 모든 크롤링 완료! 저장 작업 완료 대기 중... ({len(save_tasks)}개)")
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
                logger.info(f"{self.district_name} 전체 작업 완료: 성공 {success_count}/{total}, 실패 {fail_count}/{total}")
                # logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"{self.district_name} 크롤링 중 오류: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                await context.close()
                await browser.close()

    async def _search_and_extract(self, page: Page, store_name: str, store_address: str, road_address: str = ""):
        """네이버 지도에서 검색 및 정보 추출 (도로명 주소 우선)"""
        
        # 도로명 주소가 있는 경우 우선 검색
        if road_address and road_address.strip():
            # 1차 시도: 도로명 주소(~로/길까지) + 매장명
            road_parts = road_address.split()
            if len(road_parts) >= 2:
                # ~로, ~길까지만 추출
                road_keyword = self._extract_road_name(road_parts)
                if road_keyword:
                    first_keyword = f"{road_keyword} {store_name}"
                    # logger.info(f"1차 검색: {first_keyword}")
                    result = await self._search_single(page, first_keyword)
                    if result:
                        return result
                    
                    await asyncio.sleep(4)
                    logger.warning(f"1차 검색 실패")
            
            # 2차 시도: 도로명 전체 주소 + 매장명
            second_keyword = f"{road_address} {store_name}"
            # logger.info(f"2차 검색: {second_keyword}")
            result = await self._search_single(page, second_keyword)
            if result:
                return result
            
            await asyncio.sleep(4)
            logger.warning(f"2차 검색 실패")
        
        # 3차 시도: 지번주소(~동까지) + 가게명
        address_parts = store_address.split()
        if len(address_parts) >= 3:
            third_keyword = f"{self._extract_search_address(address_parts)} {store_name}"
        else:
            third_keyword = f"{store_address} {store_name}"
        
        # logger.info(f"3차 검색: {third_keyword}")
        result = await self._search_single(page, third_keyword)
        if result:
            return result
        
        await asyncio.sleep(4)
        logger.warning(f"3차 검색 실패")
        
        # 4차 시도: 매장명만
        # logger.info(f"4차 검색: {store_name}")
        result = await self._search_single(page, store_name)
        if result:
            return result
        
        await asyncio.sleep(4)
        logger.warning(f"4차 검색 실패")
        
        # 5차 시도: 지번 주소만
        # logger.info(f"5차 검색: {store_address}")
        result = await self._search_single(page, store_address)
        if result:
            return result
        
        await asyncio.sleep(4)
        logger.warning(f"5차 검색 실패")
        
        # 6차 시도: 지번 전체 주소 + 매장명
        sixth_keyword = f"{store_address} {store_name}"
        # logger.info(f"6차 검색: {sixth_keyword}")
        result = await self._search_single(page, sixth_keyword)
        if result:
            return result
        
        logger.error(f"모든 검색 시도 실패: {store_name}")
        return None

    def _extract_road_name(self, road_parts: List[str]) -> str:
        """도로명 주소에서 ~로, ~길까지만 추출"""
        if not road_parts:
            return ""
        
        result_parts = []
        
        for part in road_parts:
            result_parts.append(part)
            
            # ~로, ~길이 나오면 바로 종료
            if part.endswith('로') or part.endswith('길'):
                break
            
            # 안전장치: 최대 4개 요소까지
            if len(result_parts) >= 4:
                break
        
        return " ".join(result_parts)
    
    def _extract_search_address(self, address_parts: List[str]) -> str:
        """주소에서 검색에 적합한 부분 추출 (지번 주소 ~동까지)"""
        if not address_parts:
            return ""
        
        result_parts = []
        
        for part in address_parts:
            result_parts.append(part)
            
            # 읍/면/동이 나오면 바로 종료
            if part.endswith('읍') or part.endswith('면') or part.endswith('동') or part.endswith('리'):
                break
            
            # 도로명(~로, ~길)이 나오면 종료
            elif part.endswith('로') or part.endswith('길'):
                break
            
            # 안전장치: 최대 4개 요소까지
            if len(result_parts) >= 4:
                break
        
        return " ".join(result_parts)
    
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
    # 🔧 여기서 크롤링할 구를 선택하세요!
    # ========================================
    
    # 단일 구 크롤링 예시:
    # district_name = '강남구'
    # district_name = '서초구'
    # district_name = '마포구'
    
    # 또는 여러 구를 순차적으로 크롤링:
    districts_to_crawl = [
        '강남구',
        '강동구',
        '강북구',
        '강서구',
        '관악구',
        '광진구',
        '구로구',
        '금천구',
        '노원구',
        '도봉구',
        '동대문구',
        '동작구',
        '마포구',
        '서대문구',
        '서초구',
        '성동구',
        '성북구',
        '송파구',
        '양천구',
        '영등포구',
        '용산구',
        '은평구',
        '종로구',
        '중구',
        '중랑구'
    ]
    
    # ========================================
    # 크롤링 설정
    # ========================================
    headless_mode = False  # True로 설정하면 브라우저가 보이지 않음
    delay_seconds = 30     # 크롤링 간 대기 시간 (초)
    
    # ========================================
    # 크롤링 실행
    # ========================================
    
    # logger.info("=" * 80)
    # logger.info(f"크롤링 시작 - 총 {len(districts_to_crawl)}개 구")
    # logger.info(f"대상 구: {', '.join(districts_to_crawl)}")
    # logger.info("=" * 80)
    
    for idx, district_name in enumerate(districts_to_crawl, 1):
        try:
            # logger.info("")
            # logger.info("=" * 80)
            logger.info(f"[{idx}/{len(districts_to_crawl)}] {district_name} 크롤링 시작")
            # logger.info("=" * 80)
            
            # 크롤러 생성
            crawler = NaverMapDistrictCrawler(
                district_name=district_name,
                headless=headless_mode
            )
            
            # 해당 구의 API 데이터로 크롤링 시작
            await crawler.crawl_district_api(delay=delay_seconds)
            
            # logger.info("")
            # logger.info("=" * 80)
            logger.info(f"[{idx}/{len(districts_to_crawl)}] {district_name} 크롤링 완료!")
            # logger.info("=" * 80)
            
            # 다음 구로 넘어가기 전 대기 (마지막 구가 아닌 경우)
            if idx < len(districts_to_crawl):
                wait_time = 60  # 구 사이 대기 시간 (초)
                # logger.info(f"다음 구 크롤링 전 {wait_time}초 대기 중...")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            logger.error(f"{district_name} 크롤링 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 오류 발생 시에도 다음 구 진행 여부 확인
            if idx < len(districts_to_crawl):
                # logger.info(f"다음 구({districts_to_crawl[idx]})로 계속 진행합니다...")
                await asyncio.sleep(30)
    
    # logger.info("")
    # logger.info("=" * 80)
    logger.info("모든 구 크롤링 완료!")
    # logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())