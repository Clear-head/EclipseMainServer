from fastapi import APIRouter
from starlette.responses import JSONResponse

from src.logger.custom_logger import get_logger
from src.service.dashboard.dashboard_data_service import DashboardDataService

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)

dashboard_data_service = DashboardDataService()


@router.get("/monitoring")
async def monitoring():
    pass


@router.get("/test")
async def test():
    """테스트 엔드포인트 - 라우터 등록 확인용"""
    return JSONResponse(content={"message": "Admin router is working!", "path": "/admin/test"})


@router.get("/district-stats")
async def get_district_stats():
    """
    서울특별시 자치구별 매장 수 통계 조회
    
    Returns:
        JSONResponse: [{'gu': '강남구', '음식점': 268, '카페': 124, '콘텐츠': 86}, ...]
    """
    try:
        logger.info("자치구별 매장 수 조회 API 호출됨")
        result = await dashboard_data_service.get_district_stats()
        logger.info(f"자치구별 매장 수 조회 성공: {len(result)}개 구")
        return JSONResponse(content={"data": result})
    except Exception as e:
        logger.error(f"자치구별 매장 수 조회 오류: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"자치구별 매장 수 조회 중 오류가 발생했습니다: {str(e)}"}
        )