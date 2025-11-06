from typing import Tuple, List, Optional

from pydantic import BaseModel


class RequestCalculateTransPortDto(BaseModel):
    origin: Tuple[float, float]         #   출발지 좌표
    destination: Tuple[float, float]    #   도착지 좌표
    transport_type: str                 #   교통수단 타입


class PublicTransportationRoutesDto(BaseModel):
    description: str
    duration_min: int


class ResponseCalculateTransPortDto(BaseModel):
    duration: Optional[int] = None           #   이동 시간(초)
    distance: Optional[float] = None         #   이동 거리(m)
    routes: Optional[List[PublicTransportationRoutesDto]] = None   #   대중교통용

