"""
서울시 각 구의 모범음식점 API 서비스
"""
import os
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from typing import List
from dotenv import load_dotenv

from src.utils.path import path_dic
from src.logger.custom_logger import get_logger

load_dotenv(dotenv_path=path_dic["env"])
logger = get_logger(__name__)


class SeoulDistrictAPIService:
    """서울시 각 구의 모범음식점 API 서비스"""
    
    # 서울시 25개 구의 API 엔드포인트 매핑
    DISTRICT_ENDPOINTS = {
        '강남구': f'http://openAPI.gangnam.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/GnModelRestaurantDesignate',
        '강동구': f'http://openAPI.gd.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/GdModelRestaurantDesignate',
        '강북구': f'http://openAPI.gangbuk.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/GbModelRestaurantDesignate',
        '강서구': f'http://openAPI.gangseo.seoul.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/GangseoModelRestaurantDesignate',
        '관악구': f'http://openAPI.gwanak.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/GaModelRestaurantDesignate',
        '광진구': f'http://openAPI.gwangjin.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/GwangjinModelRestaurantDesignate',
        '구로구': f'http://openAPI.guro.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/GuroModelRestaurantDesignate',
        '금천구': f'http://openAPI.geumcheon.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/GeumcheonModelRestaurantDesignate',
        '노원구': f'http://openAPI.nowon.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/NwModelRestaurantDesignate',
        '도봉구': f'http://openAPI.dobong.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/DobongModelRestaurantDesignate',
        '동대문구': f'http://openAPI.ddm.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/DongdeamoonModelRestaurantDesignate',
        '동작구': f'http://openAPI.dongjak.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/DjModelRestaurantDesignate',
        '마포구': f'http://openAPI.mapo.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/MpModelRestaurantDesignate',
        '서대문구': f'http://openAPI.sdm.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/SeodaemunModelRestaurantDesignate',
        '서초구': f'http://openAPI.seocho.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/ScModelRestaurantDesignate',
        '성동구': f'http://openAPI.sd.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/SdModelRestaurantDesignate',
        '성북구': f'http://openAPI.sb.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/SbModelRestaurantDesignate',
        '송파구': f'http://openAPI.songpa.seoul.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/SpModelRestaurantDesignate',
        '양천구': f'http://openAPI.yangcheon.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/YcModelRestaurantDesignate',
        '영등포구': f'http://openAPI.ydp.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/YdpModelRestaurantDesignate',
        '용산구': f'http://openAPI.yongsan.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/YsModelRestaurantDesignate',
        '은평구': f'http://openAPI.ep.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/EpModelRestaurantDesignate',
        '종로구': f'http://openAPI.jongno.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/JongnoModelRestaurantDesignate',
        '중구': f'http://openAPI.junggu.seoul.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/JungguModelRestaurantDesignate',
        '중랑구': f'http://openAPI.jungnang.seoul.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/xml/JungnangModelRestaurantDesignate',
    }
    
    def __init__(self, district_name: str):
        """
        Args:
            district_name: 구 이름 (예: '강남구', '서초구')
        """
        self.district_name = district_name
        
        if district_name not in self.DISTRICT_ENDPOINTS:
            raise ValueError(f"지원하지 않는 구입니다: {district_name}. 지원 가능한 구: {list(self.DISTRICT_ENDPOINTS.keys())}")
        
        endpoint = self.DISTRICT_ENDPOINTS[district_name]
        self.base_url = endpoint
    
    async def fetch_all_restaurants(self) -> List[dict]:
        """
        해당 구의 모범음식점 API에서 모든 데이터 가져오기 (비동기)
        
        Returns:
            List[dict]: 음식점 데이터 리스트
        """
        try:
            # 전체 개수 확인
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f'{self.base_url}/1/1/') as response:
                    if response.status != 200:
                        logger.error(f"{self.district_name} API 호출 오류: {response.status}")
                        return []
                    
                    # XML 파싱
                    xml_text = await response.text()
                    root = ET.fromstring(xml_text)
                    
                    # 전체 개수 추출
                    total_count_elem = root.find('.//list_total_count')
                    if total_count_elem is None:
                        logger.error(f"{self.district_name} API 응답에서 list_total_count를 찾을 수 없습니다")
                        return []
                    
                    total_count = int(total_count_elem.text)
                
                # 모든 데이터 수집
                all_data = []
                batch_size = 1000
                
                tasks = []
                for start in range(1, total_count + 1, batch_size):
                    end = min(start + batch_size - 1, total_count)
                    url = f'{self.base_url}/{start}/{end}/'
                    tasks.append(self._fetch_batch(session, url, start, end))
                
                # 병렬로 데이터 수집
                batch_results = await asyncio.gather(*tasks)
                
                for batch_data in batch_results:
                    if batch_data:
                        all_data.extend(batch_data)
                
                return all_data
            
        except Exception as e:
            logger.error(f"{self.district_name} API 데이터 수집 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def _fetch_batch(self, session, url: str, start: int, end: int) -> List[dict]:
        """배치 데이터 가져오기 (XML 파싱)"""
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    # XML 파싱
                    xml_text = await response.text()
                    root = ET.fromstring(xml_text)
                    
                    # row 데이터 추출
                    rows = []
                    for row_elem in root.findall('.//row'):
                        row_data = {}
                        for child in row_elem:
                            row_data[child.tag] = child.text or ''
                        rows.append(row_data)
                    
                    return rows
                else:
                    logger.error(f"{self.district_name} 배치 {start}~{end} API 호출 오류: {response.status}")
            return []
        except Exception as e:
            logger.error(f"{self.district_name} 배치 {start}~{end} 수집 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
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
            store = {
                'id': idx,
                'name': row.get('UPSO_NM', '').strip(),
                'address': row.get('SITE_ADDR', '').strip(),  # 지번 주소
                'road_address': row.get('SITE_ADDR_RD', '').strip(),  # 도로명 주소
                'sub_category': row.get('SNT_UPTAE_NM', '').strip(),
                'admdng_nm': row.get('ADMDNG_NM', '').strip(),
                'main_edf': row.get('MAIN_EDF', '').strip(),
                'original_data': row
            }
            converted_data.append(store)
        
        return converted_data