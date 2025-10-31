"""
네이버 지도 검색 전략 모듈
다양한 검색 키워드 조합으로 매장을 찾는 전략을 제공합니다.
"""
import asyncio
from typing import List

from playwright.async_api import Page, TimeoutError

from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


class NaverMapSearchStrategy:
    """네이버 지도 검색 전략 클래스"""
    
    def __init__(self, naver_map_url: str = "https://map.naver.com/v5/search"):
        self.naver_map_url = naver_map_url
    
    @staticmethod
    def extract_road_name(address: str) -> str:
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
    
    @staticmethod
    def extract_dong_name(address: str) -> str:
        """
        주소에서 동/읍/면/리까지만 추출
        
        Args:
            address: 전체 주소
            
        Returns:
            str: 동/읍/면/리까지의 주소
        """
        if not address:
            return ""
        
        address_parts = address.split()
        result_parts = []
        
        for part in address_parts:
            result_parts.append(part)
            
            # 읍/면/동/리가 나오면 바로 종료
            if part.endswith('읍') or part.endswith('면') or part.endswith('동') or part.endswith('리'):
                break
            
            # 도로명(~로, ~길)이 나오면 종료
            elif part.endswith('로') or part.endswith('길'):
                break
            
            # 안전장치: 최대 4개 요소까지
            if len(result_parts) >= 4:
                break
        
        return " ".join(result_parts)
    
    async def search_with_multiple_strategies(
        self, 
        page: Page, 
        store_name: str, 
        store_address: str = "",
        road_address: str = "",
        extractor_callback = None
    ):
        """
        여러 검색 전략을 시도하여 매장 정보 추출
        
        Args:
            page: Playwright Page 객체
            store_name: 매장명
            store_address: 지번 주소
            road_address: 도로명 주소 (선택)
            extractor_callback: 검색 성공 시 정보 추출 콜백 함수
            
        Returns:
            매장 정보 또는 None
        """
        strategies = self._build_search_strategies(store_name, store_address, road_address)
        
        for idx, (strategy_name, keyword) in enumerate(strategies, 1):
            if not keyword:  # 빈 키워드는 스킵
                continue
            
            logger.info(f"  {idx}차 검색 ({strategy_name}): {keyword}")
            result = await self._search_single(page, keyword, extractor_callback)
            
            if result:
                logger.info(f"  {idx}차 검색 성공!")
                return result
            
            await asyncio.sleep(4)
            logger.warning(f"  {idx}차 검색 실패")
        
        logger.error(f"  모든 검색 시도 실패: {store_name}")
        return None
    
    def _build_search_strategies(
        self, 
        store_name: str, 
        store_address: str, 
        road_address: str
    ) -> List[tuple]:
        """
        검색 전략 목록 생성
        
        Returns:
            List[Tuple[str, str]]: [(전략명, 검색키워드), ...]
        """
        strategies = []
        
        # 도로명 주소 기반 검색
        if road_address and road_address.strip():
            road_name = self.extract_road_name(road_address)
            if road_name:
                strategies.append(("도로명(~로/길) + 매장명", f"{road_name} {store_name}"))
            strategies.append(("도로명 전체 + 매장명", f"{road_address} {store_name}"))
        
        # 지번 주소 기반 검색
        if store_address:
            dong_name = self.extract_dong_name(store_address)
            if dong_name:
                strategies.append(("지번(~동) + 매장명", f"{dong_name} {store_name}"))
        
        # 매장명만
        strategies.append(("매장명", store_name))
        
        # 주소만
        if store_address:
            strategies.append(("지번 주소", store_address))
            strategies.append(("지번 전체 + 매장명", f"{store_address} {store_name}"))
        
        return strategies
    
    async def _search_single(self, page: Page, keyword: str, extractor_callback):
        """
        단일 키워드로 검색
        
        Args:
            page: Playwright Page 객체
            keyword: 검색 키워드
            extractor_callback: 정보 추출 콜백 함수
        """
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
            
            # 정보 추출 (콜백이 제공된 경우)
            if extractor_callback:
                return await extractor_callback(entry_frame, page)
            
            return True  # 검색 성공
            
        except TimeoutError:
            logger.error(f"'{keyword}' 검색 결과를 찾을 수 없습니다.")
            return None
        except Exception as e:
            logger.error(f"'{keyword}' 검색 중 오류: {e}")
            return None