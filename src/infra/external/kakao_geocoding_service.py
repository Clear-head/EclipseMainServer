"""
카카오 로컬 API를 사용한 주소 -> 좌표 변환 서비스
"""
import os
import asyncio
import aiohttp
from typing import Optional, Tuple
from dotenv import load_dotenv

from src.utils.path import path_dic
from src.logger.custom_logger import get_logger

load_dotenv(dotenv_path=path_dic["env"])
logger = get_logger(__name__)

class GeocodingService:
    """카카오 로컬 API를 사용한 주소 -> 좌표 변환 서비스"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('KAKAO_REST_API_KEY')
        
        if not self.api_key:
            logger.warning("카카오 REST API 키가 없습니다. 좌표 변환 기능이 비활성화됩니다.")
        
        self.base_url = "https://dapi.kakao.com/v2/local/search/address.json"
        self.headers = {
            "Authorization": f"KakaoAK {self.api_key}"
        }
    
    async def get_coordinates(self, address: str, max_retries: int = 5) -> Tuple[Optional[str], Optional[str]]:
        """
        주소를 좌표(경도, 위도)로 변환 (비동기)
        
        Args:
            address: 변환할 주소
            max_retries: 최대 재시도 횟수
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (경도, 위도) 또는 (None, None)
        """
        if not self.api_key:
            logger.warning("API 키가 없어 좌표 변환을 건너뜁니다.")
            return None, None
        
        if not address or not address.strip():
            logger.warning("주소가 비어있습니다.")
            return None, None
        
        params = {
            "query": address
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        self.base_url,
                        headers=self.headers,
                        params=params
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            
                            if result.get('documents') and len(result['documents']) > 0:
                                doc = result['documents'][0]
                                longitude = str(doc['x'])  # 경도 (문자열)
                                latitude = str(doc['y'])   # 위도 (문자열)
                                return longitude, latitude
                            else:
                                logger.warning(f"주소에 대한 좌표를 찾을 수 없습니다: {address}")
                                return None, None
                                
                        elif response.status == 401:
                            logger.error("카카오 API 인증 실패. API 키를 확인하세요.")
                            return None, None
                            
                        else:
                            logger.warning(f"✗ 좌표 변환 실패 ({attempt}번째 시도) - 상태 코드: {response.status}")
                            
                            if attempt < max_retries:
                                await asyncio.sleep(3)
                            else:
                                logger.error(f"✗ 최대 재시도 횟수 초과")
                                return None, None
                        
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(1)
                else:
                    logger.error(f"✗ 최대 재시도 횟수 초과")
                    return None, None
                    
            except Exception as e:
                logger.error(f"✗ 좌표 변환 중 오류 ({attempt}번째 시도): {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(1)
                else:
                    return None, None
        
        return None, None