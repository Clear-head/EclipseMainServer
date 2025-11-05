"""
경로별 이동시간 계산 서비스 (자동차, 대중교통, 도보)
"""

import os
from typing import Dict, Optional, List
import requests
from dotenv import load_dotenv

from src.utils.path import path_dic
from src.logger.custom_logger import get_logger

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
    
    async def calculate_all_routes(
        self,
        origin: str,
        destination: str
    ) -> Dict[str, Optional[Dict]]:
        """
        모든 교통수단에 대한 경로 계산
        
        [입력]
            origin: 출발지 좌표 "경도,위도" 형식
                   예: "126.9707878,37.5542776"
            destination: 도착지 좌표 "경도,위도" 형식
                        예: "126.9232185,37.5571891"
            
        [출력]
            {
                'car': {
                    'duration_minutes': 15,      # 소요 시간 (분)
                    'distance_km': 5.2,          # 거리 (km)
                    'duration_seconds': 900,     # 소요 시간 (초)
                    'distance_meters': 5200      # 거리 (m)
                },
                'transit': {
                    'duration_minutes': 25,      # 소요 시간 (분)
                    'fare': 1400,                # 요금 (원)
                    'transfer_count': 1,         # 환승 횟수
                    'distance_km': 6.3,          # 거리 (km)
                    'duration_seconds': 1500,    # 소요 시간 (초)
                    'distance_meters': 6300,     # 거리 (m)
                    'routes': [...]              # 상세 경로 정보
                },
                'walk': {
                    'duration_minutes': 45,      # 소요 시간 (분)
                    'distance_km': 3.5,          # 거리 (km)
                    'duration_seconds': 2700,    # 소요 시간 (초)
                    'distance_meters': 3500      # 거리 (m)
                }
            }
            
            * API 호출 실패 시 해당 교통수단은 None으로 반환
        """
        logger.info(f"경로 계산 시작 - 출발: {origin}, 도착: {destination}")
        
        results = {
            'car': await self._get_car_route(origin, destination),
            'transit': await self._get_transit_route(origin, destination),
            'walk': await self._get_walk_route(origin, destination)
        }
        
        logger.info(f"경로 계산 완료: {results}")
        return results
    
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
                        'type': 'WALK',          # 경로 타입 (WALK, SUBWAY, BUS)
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
    
    def _parse_transit_legs(self, legs: List[Dict]) -> List[Dict]:
        """
        대중교통 상세 경로 파싱
        
        [입력]
            legs: Tmap API의 경로 구간 리스트
                  예: [
                      {'mode': 'WALK', 'distance': 300, 'sectionTime': 360, ...},
                      {'mode': 'SUBWAY', 'route': '2호선', 'start': {...}, 'end': {...}, ...},
                      ...
                  ]
        
        [출력]
            파싱된 경로 정보 리스트:
            [
                {
                    'type': 'WALK',              # 구간 타입
                    'description': '도보 300m',   # 설명
                    'duration_minutes': 5,       # 소요 시간 (분)
                    'distance_meters': 300       # 거리 (m)
                },
                {
                    'type': 'SUBWAY',
                    'route_name': '2호선',
                    'description': '2호선: 홍대입구역 → 신촌역',
                    'start_station': '홍대입구역',
                    'end_station': '신촌역',
                    'station_count': 1,          # 정거장 수
                    'duration_minutes': 3,
                    'distance_meters': 1200
                },
                ...
            ]
        """
        parsed_routes = []
        
        for leg in legs:
            mode = leg['mode']
            
            # 도보 구간
            if mode == 'WALK':
                parsed_routes.append({
                    'type': 'WALK',
                    'description': f"도보 {leg['distance']}m",
                    'duration_minutes': leg['sectionTime'] // 60,
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
                    'duration_minutes': leg['sectionTime'] // 60,
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
                    'duration_minutes': leg['sectionTime'] // 60,
                    'distance_meters': leg['distance']
                })
        
        return parsed_routes
    
    async def calculate_route_for_segments(
        self,
        waypoints: List[str]
    ) -> List[Dict[str, Optional[Dict]]]:
        """
        여러 구간의 경로를 한 번에 계산 (일정표용)
        
        [입력]
            waypoints: 좌표 리스트
                      예: [
                          "126.9707878,37.5542776",  # 출발지 (집)
                          "126.9232185,37.5571891",  # 첫 번째 장소 (카페)
                          "126.9334567,37.5623456",  # 두 번째 장소 (음식점)
                          "126.9445678,37.5734567"   # 세 번째 장소 (영화관)
                      ]
            
        [출력]
            구간별 경로 정보 리스트:
            [
                {
                    'segment_index': 0,                      # 구간 번호 (0부터 시작)
                    'origin': "126.9707878,37.5542776",     # 출발지 좌표
                    'destination': "126.9232185,37.5571891", # 도착지 좌표
                    'car': {...},                           # 자동차 경로
                    'transit': {...},                       # 대중교통 경로
                    'walk': {...}                           # 도보 경로
                },
                {
                    'segment_index': 1,
                    'origin': "126.9232185,37.5571891",
                    'destination': "126.9334567,37.5623456",
                    'car': {...},
                    'transit': {...},
                    'walk': {...}
                },
                ...
            ]
        """
        results = []
        
        # 각 구간별로 경로 계산
        for i in range(len(waypoints) - 1):
            origin = waypoints[i]
            destination = waypoints[i + 1]
            
            # 모든 교통수단의 경로 계산
            routes = await self.calculate_all_routes(origin, destination)
            
            results.append({
                'segment_index': i,
                'origin': origin,
                'destination': destination,
                **routes
            })
        
        return results


# ========== 테스트용 함수 ==========
async def test_route_calculation():
    """
    경로 계산 테스트 함수
    
    [입력] 없음
    [출력] 콘솔에 경로 계산 결과 출력
    """
    service = RouteCalculationService()
    
    # 예시: 서울역 -> 홍대입구역
    origin = "126.9707878,37.5542776"
    destination = "126.9232185,37.5571891"
    
    results = await service.calculate_all_routes(origin, destination)
    
    print("\n" + "="*60)
    print("경로 계산 결과")
    print("="*60)
    
    # 자동차 경로 출력
    if results['car']:
        print(f"\n🚗 자동차:")
        print(f"  소요시간: {results['car']['duration_minutes']}분")
        print(f"  거리: {results['car']['distance_km']}km")
    
    # 대중교통 경로 출력
    if results['transit']:
        print(f"\n🚌 대중교통:")
        print(f"  소요시간: {results['transit']['duration_minutes']}분")
        print(f"  요금: {results['transit']['fare']:,}원")
        print(f"  환승: {results['transit']['transfer_count']}회")
        print(f"\n  상세 경로:")
        for i, route in enumerate(results['transit']['routes'], 1):
            print(f"    {i}. {route['description']} ({route['duration_minutes']}분)")
    
    # 도보 경로 출력
    if results['walk']:
        print(f"\n🚶 도보:")
        print(f"  소요시간: {results['walk']['duration_minutes']}분")
        print(f"  거리: {results['walk']['distance_km']}km")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_route_calculation())