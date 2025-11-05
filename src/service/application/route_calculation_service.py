"""
경로별 이동시간 계산 서비스 (자동차, 대중교통, 도보)
사용자가 버튼을 누를 때마다 해당 교통수단의 경로를 실시간으로 계산
"""

import os
from typing import Dict, Optional, Tuple

import requests
from dotenv import load_dotenv

from src.logger.custom_logger import get_logger
from src.utils.path import path_dic

load_dotenv(dotenv_path=path_dic["env"])
logger = get_logger(__name__)


class RouteCalculationService:
    """
    카카오 모빌리티 API와 Tmap API를 사용한 경로 계산 서비스
    """
    
    def __init__(self):
        """
        서비스 초기화 - API 키 로드
        """
        self.kakao_key = os.getenv('KAKAO_REST_API_KEY')
        self.tmap_key = os.getenv('TMAP_KEY')
        
        if not self.kakao_key:
            logger.warning("KAKAO_REST_API_KEY가 설정되지 않았습니다.")
        if not self.tmap_key:
            logger.warning("TMAP_KEY가 설정되지 않았습니다.")
    
    async def calculate_route_by_transport_type(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        transport_type: int
    ) -> Optional[Dict]:
        """
        선택한 교통수단의 경로만 계산 (버튼 클릭 시 호출)
        
        [입력]
            origin: 출발지 좌표 (경도, 위도)
                   예: (126.9707878, 37.5542776)
            destination: 도착지 좌표 (경도, 위도)
                        예: (126.9232185, 37.5571891)
            transport_type: 교통수단 타입
                           0 = 도보
                           1 = 대중교통
                           2 = 자동차
            
        [출력]
            도보(0) 선택 시:
            {
                'transport_type': 0,
                'transport_name': '도보',
                'duration_minutes': 45,      # 소요 시간 (분)
                'distance_km': 3.5,          # 거리 (km)
                'duration_seconds': 2700,    # 소요 시간 (초)
                'distance_meters': 3500      # 거리 (m)
            }
            
            대중교통(1) 선택 시:
            {
                'transport_type': 1,
                'transport_name': '대중교통',
                'duration_minutes': 25,      # 소요 시간 (분)
                'fare': 1400,                # 요금 (원)
                'transfer_count': 1,         # 환승 횟수
                'distance_km': 6.3,          # 거리 (km)
                'duration_seconds': 1500,    # 소요 시간 (초)
                'distance_meters': 6300,     # 거리 (m)
                'routes': [...]              # 상세 경로 정보
            }
            
            자동차(2) 선택 시:
            {
                'transport_type': 2,
                'transport_name': '자동차',
                'duration_minutes': 15,      # 소요 시간 (분)
                'distance_km': 5.2,          # 거리 (km)
                'duration_seconds': 900,     # 소요 시간 (초)
                'distance_meters': 5200      # 거리 (m)
            }
            
            실패 시: None
        """
        # 좌표를 문자열로 변환
        origin_str = f"{origin[0]},{origin[1]}"
        destination_str = f"{destination[0]},{destination[1]}"
        
        logger.info(f"경로 계산 요청 - 교통수단: {transport_type}, 출발: {origin_str}, 도착: {destination_str}")
        
        # 교통수단별 계산
        if transport_type == 0:  # 도보
            result = await self._get_walk_route(origin_str, destination_str)
            if result:
                result['transport_type'] = 0
                result['transport_name'] = '도보'
            return result
            
        elif transport_type == 1:  # 대중교통
            result = await self._get_transit_route(origin_str, destination_str)
            if result:
                result['transport_type'] = 1
                result['transport_name'] = '대중교통'
            return result
            
        elif transport_type == 2:  # 자동차
            result = await self._get_car_route(origin_str, destination_str)
            if result:
                result['transport_type'] = 2
                result['transport_name'] = '자동차'
            return result
            
        else:
            logger.error(f"잘못된 교통수단 타입: {transport_type}")
            return None
    
    async def _get_car_route(
        self,
        origin: str,
        destination: str
    ) -> Optional[Dict]:
        """
        자동차 경로 계산 (카카오 모빌리티 API 사용)
        
        [입력]
            origin: 출발지 좌표 "경도,위도"
            destination: 도착지 좌표 "경도,위도"
        
        [출력]
            성공 시:
            {
                'duration_minutes': 15,      # 소요 시간 (분)
                'distance_km': 5.2,          # 거리 (km)
                'duration_seconds': 900,     # 소요 시간 (초)
                'distance_meters': 5200      # 거리 (m)
            }
            
            실패 시: None
        """
        if not self.kakao_key:
            logger.error("카카오 API 키가 없어 자동차 경로를 계산할 수 없습니다.")
            return None
        
        try:
            response = requests.get(
                'https://apis-navi.kakaomobility.com/v1/directions',
                headers={'Authorization': f'KakaoAK {self.kakao_key}'},
                params={
                    'origin': origin,
                    'destination': destination
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                route = data['routes'][0]['summary']
                
                result = {
                    'duration_minutes': route['duration'] // 60,
                    'distance_km': round(route['distance'] / 1000, 1),
                    'duration_seconds': route['duration'],
                    'distance_meters': route['distance']
                }
                
                logger.info(f"자동차: {result['duration_minutes']}분 ({result['distance_km']}km)")
                return result
            else:
                logger.error(f"자동차 경로 조회 실패: 상태코드 {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"자동차 경로 계산 중 오류: {e}")
            return None
    
    async def _get_transit_route(
        self,
        origin: str,
        destination: str
    ) -> Optional[Dict]:
        """
        대중교통 경로 계산 (Tmap API 사용)
        
        [입력]
            origin: 출발지 좌표 "경도,위도"
            destination: 도착지 좌표 "경도,위도"
        
        [출력]
            성공 시:
            {
                'duration_minutes': 25,          # 소요 시간 (분)
                'fare': 1400,                    # 요금 (원)
                'transfer_count': 1,             # 환승 횟수
                'distance_km': 6.3,              # 거리 (km)
                'duration_seconds': 1500,        # 소요 시간 (초)
                'distance_meters': 6300,         # 거리 (m)
                'routes': [                      # 상세 경로 정보
                    {
                        'type': 'WALK',
                        'description': '도보 300m',
                        'duration_minutes': 5,
                        'distance_meters': 300
                    },
                    {
                        'type': 'SUBWAY',
                        'route_name': '2호선',
                        'description': '2호선: 홍대입구역 → 신촌역',
                        'start_station': '홍대입구역',
                        'end_station': '신촌역',
                        'station_count': 1,
                        'duration_minutes': 3,
                        'distance_meters': 1200
                    },
                    ...
                ]
            }
            
            실패 시: None
        """
        if not self.tmap_key:
            logger.error("Tmap API 키가 없어 대중교통 경로를 계산할 수 없습니다.")
            return None
        
        try:
            # 좌표 분리 (경도, 위도)
            start_x, start_y = origin.split(',')
            end_x, end_y = destination.split(',')
            
            response = requests.post(
                'https://apis.openapi.sk.com/transit/routes',
                headers={
                    'accept': 'application/json',
                    'appKey': self.tmap_key,
                    'Content-Type': 'application/json'
                },
                json={
                    'startX': start_x,
                    'startY': start_y,
                    'endX': end_x,
                    'endY': end_y,
                    'format': 'json',
                    'count': 1  # 최적 경로 1개만 요청
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # 응답 데이터에서 경로 정보 추출
                if 'metaData' in data and 'plan' in data['metaData']:
                    itinerary = data['metaData']['plan']['itineraries'][0]
                    
                    total_time = itinerary['totalTime']
                    total_fare = itinerary['fare']['regular']['totalFare']
                    transfer_count = itinerary['transferCount']
                    total_distance = itinerary['totalDistance']
                    
                    # 상세 경로 파싱
                    routes = self._parse_transit_legs(itinerary['legs'])
                    
                    result = {
                        'duration_minutes': total_time // 60,
                        'fare': total_fare,
                        'transfer_count': transfer_count,
                        'distance_km': round(total_distance / 1000, 1),
                        'duration_seconds': total_time,
                        'distance_meters': total_distance,
                        'routes': routes
                    }
                    
                    transfer_text = f", 환승 {transfer_count}회" if transfer_count > 0 else ", 직통"
                    logger.info(f"대중교통: {result['duration_minutes']}분 ({result['fare']:,}원{transfer_text})")
                    return result
                else:
                    logger.warning("대중교통 경로 없음")
                    return None
            else:
                logger.error(f"대중교통 경로 조회 실패: 상태코드 {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"대중교통 경로 계산 중 오류: {e}")
            return None
    
    async def _get_walk_route(
        self,
        origin: str,
        destination: str
    ) -> Optional[Dict]:
        """
        도보 경로 계산 (Tmap API 사용)
        
        [입력]
            origin: 출발지 좌표 "경도,위도"
            destination: 도착지 좌표 "경도,위도"
        
        [출력]
            성공 시:
            {
                'duration_minutes': 45,      # 소요 시간 (분)
                'distance_km': 3.5,          # 거리 (km)
                'duration_seconds': 2700,    # 소요 시간 (초)
                'distance_meters': 3500      # 거리 (m)
            }
            
            실패 시: None
        """
        if not self.tmap_key:
            logger.error("Tmap API 키가 없어 도보 경로를 계산할 수 없습니다.")
            return None
        
        try:
            # 좌표 분리 (경도, 위도)
            start_x, start_y = origin.split(',')
            end_x, end_y = destination.split(',')
            
            response = requests.post(
                'https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1',
                headers={
                    'appKey': self.tmap_key,
                    'Content-Type': 'application/json'
                },
                json={
                    'startX': start_x,
                    'startY': start_y,
                    'endX': end_x,
                    'endY': end_y,
                    'startName': '출발',
                    'endName': '도착'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                properties = data['features'][0]['properties']
                
                result = {
                    'duration_minutes': properties['totalTime'] // 60,
                    'distance_km': round(properties['totalDistance'] / 1000, 1),
                    'duration_seconds': properties['totalTime'],
                    'distance_meters': properties['totalDistance']
                }
                
                logger.info(f"도보: {result['duration_minutes']}분 ({result['distance_km']}km)")
                return result
            else:
                logger.error(f"도보 경로 조회 실패: 상태코드 {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"도보 경로 계산 중 오류: {e}")
            return None
    
    def _parse_transit_legs(self, legs: list) -> list:
        """
        대중교통 상세 경로 파싱 (각 구간별 소요 시간 포함)
        """
        parsed_routes = []
        
        for leg in legs:
            mode = leg['mode']
            duration_sec = leg['sectionTime']  # 초 단위
            duration_min = duration_sec // 60   # 분 단위
            
            # 도보 구간
            if mode == 'WALK':
                start_name = leg.get('start', {}).get('name', '출발지')
                end_name = leg.get('end', {}).get('name', '도착지')
                
                parsed_routes.append({
                    'type': 'WALK',
                    'description': f"도보",
                    'start_point': start_name,  # ✅ 추가
                    'end_point': end_name,      # ✅ 추가
                    'duration_minutes': duration_min,
                    'duration_seconds': duration_sec,  # ✅ 초 단위 추가
                    'distance_meters': leg['distance']
                })
            
            # 지하철 구간
            elif mode == 'SUBWAY':
                route = leg['route']
                start_station = leg['start']['name']
                end_station = leg['end']['name']
                station_count = len(leg['passStopList']['stations']) - 1
                
                parsed_routes.append({
                    'type': 'SUBWAY',
                    'route_name': route,
                    'description': f"{route}: {start_station} → {end_station}",
                    'start_station': start_station,
                    'end_station': end_station,
                    'station_count': station_count,
                    'duration_minutes': duration_min,
                    'duration_seconds': duration_sec,  # ✅ 초 단위 추가
                    'distance_meters': leg['distance']
                })
            
            # 버스 구간
            elif mode == 'BUS':
                route = leg.get('route', '버스')
                start_stop = leg['start']['name']
                end_stop = leg['end']['name']
                
                parsed_routes.append({
                    'type': 'BUS',
                    'route_name': route,
                    'description': f"{route}번 버스: {start_stop} → {end_stop}",
                    'start_stop': start_stop,
                    'end_stop': end_stop,
                    'duration_minutes': duration_min,
                    'duration_seconds': duration_sec,  # ✅ 초 단위 추가
                    'distance_meters': leg['distance']
                })
        
        return parsed_routes

