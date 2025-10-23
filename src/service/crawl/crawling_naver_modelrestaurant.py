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


# 외부 API 서비스 import
from src.infra.external.seoul_district_api_service import SeoulDistrictAPIService
from src.infra.external.kakao_geocoding_service import GeocodingService
from src.infra.external.category_classifier_service import CategoryTypeClassifier

# 유틸리티 import
from src.service.crawl.utils.address_parser import AddressParser
from src.service.crawl.utils.store_detail_extractor import StoreDetailExtractor
from src.service.crawl.utils.store_data_saver import StoreDataSaver
from src.service.crawl.utils.search_strategy import NaverMapSearchStrategy
from src.service.crawl.utils.crawling_manager import CrawlingManager


class NaverMapDistrictCrawler:
    """서울시 각 구 API 데이터 크롤링 클래스"""
    
    def __init__(self, district_name: str, logger, headless: bool = False):
        self.district_name = district_name
        self.headless = headless
        self.logger = logger
        self.naver_map_url = "https://map.naver.com/v5/search"
        self.geocoding_service = GeocodingService()
        self.category_classifier = CategoryTypeClassifier()
        
        # logger를 외부 서비스에도 전달
        self.geocoding_service = GeocodingService(logger=logger)
        self.category_classifier = CategoryTypeClassifier(logger=logger)
        
        # logger를 유틸리티 클래스에 전달
        self.data_saver = StoreDataSaver(logger)
        self.search_strategy = NaverMapSearchStrategy(logger)
        self.crawling_manager = CrawlingManager(district_name, logger)
    
    async def crawl_district_api(self, delay: int = 20):
        """해당 구의 API에서 데이터를 가져와 크롤링"""
        # API 데이터 가져오기
        api_service = SeoulDistrictAPIService(self.district_name, logger=self.logger)
        api_data = await api_service.fetch_all_restaurants()
        
        if not api_data:
            self.logger.warning(f"{self.district_name} API에서 데이터를 가져올 수 없습니다.")
            return
        
        stores = api_service.convert_to_store_format(api_data)
        
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
                # 크롤링 매니저를 사용한 병렬 처리
                await self.crawling_manager.execute_crawling_with_save(
                    stores=stores,
                    crawl_func=lambda store, idx, total: self._crawl_single_store(page, store),
                    save_func=self._save_wrapper,
                    delay=delay
                )
                
            except Exception as e:
                self.logger.error(f"{self.district_name} 크롤링 중 오류: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                await context.close()
                await browser.close()
    
    async def _crawl_single_store(self, page: Page, store: dict):
        """단일 매장 크롤링"""
        store_name = store['name']
        store_address = store['address']
        road_address = store['road_address']
        
        # 검색 전략 사용
        async def extract_callback(entry_frame, page):
            extractor = StoreDetailExtractor(entry_frame, page, self.logger)
            return await extractor.extract_all_details()
        
        return await self.search_strategy.search_with_multiple_strategies(
            page=page,
            store_name=store_name,
            store_address=store_address,
            road_address=road_address,
            extractor_callback=extract_callback
        )
    
    async def _save_wrapper(self, idx: int, total: int, store_data: tuple, store_name: str):
        """저장 래퍼"""
        return await self.data_saver.save_store_data(
            idx=idx,
            total=total,
            store_data=store_data,
            store_name=store_name,
            log_prefix=self.district_name
        )


async def main():
    """메인 함수"""
    
    # ========================================
    # 로거 초기화 (한 번만)
    # ========================================
    logger = get_logger('crawling_naver_model')
    
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
    
    for idx, district_name in enumerate(districts_to_crawl, 1):
        try:
            logger.info(f"[{idx}/{len(districts_to_crawl)}] {district_name} 크롤링 시작")
            
            # 크롤러 생성 (logger 전달)
            crawler = NaverMapDistrictCrawler(
                district_name=district_name,
                logger=logger,
                headless=headless_mode
            )
            
            # 해당 구의 API 데이터로 크롤링 시작
            await crawler.crawl_district_api(delay=delay_seconds)
            
            logger.info(f"[{idx}/{len(districts_to_crawl)}] {district_name} 크롤링 완료!")
            
            # 다음 구로 넘어가기 전 대기 (마지막 구가 아닌 경우)
            if idx < len(districts_to_crawl):
                wait_time = 60  # 구 사이 대기 시간 (초)
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            logger.error(f"{district_name} 크롤링 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 오류 발생 시에도 다음 구 진행 여부 확인
            if idx < len(districts_to_crawl):
                await asyncio.sleep(30)
    
    logger.info("모든 구 크롤링 완료!")
    
    
if __name__ == "__main__":
    asyncio.run(main())