from typing import Tuple, List, Optional

from pydantic import BaseModel


# 교통 경로 계산

class RequestCalculateTransportDTO(BaseModel):
    origin: Tuple[float, float]         # 출발지 좌표 (경도, 위도)
    destination: Tuple[float, float]    # 도착지 좌표 (경도, 위도)
    transport_type: str                 # 교통수단 타입 (0: 도보, 1: 대중교통, 2: 자동차)


class PublicTransportRouteDTO(BaseModel):
    description: str
    duration_min: int


class ResponseCalculateTransportDTO(BaseModel):
    duration: Optional[int] = None                               # 이동 시간 (초)
    distance: Optional[float] = None                             # 이동 거리 (m)
    routes: Optional[List[PublicTransportRouteDTO]] = None       # 대중교통용 상세 경로