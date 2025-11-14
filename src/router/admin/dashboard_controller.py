from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
from starlette.responses import JSONResponse

from src.logger.custom_logger import get_logger
from src.service.dashboard.dashboard_data_service import DashboardDataService

# HTML 파일 서빙용 router (prefix 없음 - 루트 경로)
html_router = APIRouter(tags=["dashboard"])

# 대시보드 API용 router (prefix="/admin")
api_router = APIRouter(prefix="/admin", tags=["dashboard"])

logger = get_logger(__name__)

# HTML 파일 경로
resources_path = Path(__file__).parent.parent.parent / "resources" / "html"

# 대시보드 데이터 서비스
dashboard_data_service = DashboardDataService()


# HTML 파일 서빙
@html_router.get("/")
async def root():
    """루트 경로 - 대시보드로 리다이렉트"""
    return FileResponse(resources_path / "dashboard.html")


@html_router.get("/dashboard.html")
async def dashboard():
    """대시보드 페이지"""
    return FileResponse(resources_path / "dashboard.html")


@html_router.get("/data.html")
async def data():
    """데이터 관리 페이지"""
    return FileResponse(resources_path / "data.html")


@html_router.get("/users.html")
async def users():
    """사용자 관리 페이지"""
    return FileResponse(resources_path / "users.html")


# 정적 파일 서빙 (CSS, JS)
@html_router.get("/styles.css")
async def styles():
    """CSS 파일"""
    return FileResponse(resources_path / "styles.css", media_type="text/css")


@html_router.get("/api.js")
async def api_js():
    """API JavaScript 파일"""
    return FileResponse(resources_path / "api.js", media_type="application/javascript")


# 대시보드 데이터 API
@api_router.get("/district-stats")
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


# 두 router를 하나로 합치기 (main.py에서 사용)
router = html_router
api_router_instance = api_router

