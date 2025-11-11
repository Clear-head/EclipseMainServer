"""
공공데이터포털 맛집 API 서비스
"""
import asyncio
import os
from typing import List

import aiohttp
from dotenv import load_dotenv

from src.logger.custom_logger import get_logger
from src.utils.path import path_dic

load_dotenv(dotenv_path=path_dic["env"])
logger = get_logger(__name__)


class PublicDataAPIService:
    """공공데이터포털 맛집 API 서비스"""
    
    def __init__(self):
        self.base_url = "https://api.odcloud.kr/api/15117214/v1/uddi:ece1bb97-4e89-431a-a6af-935d8d2c1d60"
        self.service_key = os.getenv("DATA_GO_KR")
        self.per_page = 500
    
    async def fetch_seoul_restaurants(self) -> List[dict]:
        """
        공공데이터포털 API에서 서울특별시 맛집 데이터만 가져오기 (비동기)
        서울특별시가 아닌 데이터가 나오면 즉시 종료
        
        Returns:
            List[dict]: 서울특별시 맛집 데이터 리스트
        """
        seoul_data = []
        page = 1
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                while True:
                    logger.info(f"공공데이터 API 페이지 {page} 수집 중...")
                    
                    params = {
                        'page': page,
                        'perPage': self.per_page,
                        'serviceKey': self.service_key
                    }
                    
                    async with session.get(self.base_url, params=params) as response:
                        if response.status != 200:
                            logger.error(f"API 호출 오류: {response.status}")
                            break
                        
                        data = await response.json()
                        
                        # 데이터 추출
                        items = data.get('data', [])
                        if not items:
                            logger.info(f"페이지 {page}에서 데이터 없음, 수집 종료")
                            break
                        
                        # 서울특별시 데이터만 필터링 및 조기 종료 체크
                        seoul_count = 0
                        for item in items:
                            address = item.get('주소', '')
                            
                            if address and address.startswith('서울특별시'):
                                seoul_data.append(item)
                                seoul_count += 1
                            else:
                                # 서울특별시가 아닌 데이터 발견 시 즉시 종료
                                if address:
                                    logger.info(f"서울특별시가 아닌 데이터 발견: {address}")
                                    logger.info(f"페이지 {page}에서 수집 종료")
                                    logger.info(f"총 {len(seoul_data)}개 서울특별시 맛집 데이터 수집 완료")
                                    return seoul_data
                        
                        logger.info(f"페이지 {page}: 서울특별시 {seoul_count}개 수집 (누적: {len(seoul_data)}개)")
                        
                        # 현재 페이지 개수가 perPage보다 적으면 마지막 페이지
                        current_count = data.get('currentCount', 0)
                        if current_count < self.per_page:
                            logger.info(f"마지막 페이지 도달, 총 {len(seoul_data)}개 서울특별시 맛집 수집 완료")
                            break
                        
                        page += 1
                        await asyncio.sleep(1)  # API 부하 방지
            
            logger.info(f"공공데이터포털 API에서 총 {len(seoul_data)}개 서울특별시 맛집 데이터 수집 완료")
            return seoul_data
            
        except Exception as e:
            logger.error(f"공공데이터 API 수집 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return seoul_data
    
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
    
    def convert_to_store_format(self, api_data: List[dict]) -> List[dict]:
        """
        API 데이터를 크롤링용 포맷으로 변환
        
        Args:
            api_data: API에서 가져온 원본 데이터
            
        Returns:
            List[dict]: 변환된 상점 데이터
        """
        converted_data = []
        
        for idx, row in enumerate(api_data, 1):
            full_address = row.get('주소', '').strip()
            road_address = self.extract_road_name(full_address)
            
            store = {
                'id': idx,
                'name': row.get('상호', '').strip(),
                'address': full_address,  # 전체 주소
                'road_address': road_address,  # 도로명(~로/~길)까지
                'menu': row.get('메뉴', '').strip(),
                'category': row.get('업종', '').strip(),
                'original_data': row
            }
            converted_data.append(store)
        
        logger.info(f"{len(converted_data)}개 상점 데이터 변환 완료")
        return converted_data