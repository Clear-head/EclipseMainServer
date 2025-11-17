from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from src.logger.custom_logger import get_logger
from src.service.dashboard.dashboard_data_service import DashboardDataService
from src.service.dashboard.dashboard_service import DashboardService
from src.service.dashboard.dashboard_user_service import DashboardUserService

router = APIRouter()
logger = get_logger(__name__)

dashboard_data_service = DashboardDataService()
dashboard_service = DashboardService()
dashboard_user_service = DashboardUserService()


@router.get("/dashboard/data", response_class=HTMLResponse)
async def get_data_page():
    """데이터 관리 페이지 반환"""
    html_path = Path(__file__).parent.parent.parent / "resources" / "html" / "data.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/dashboard.html", response_class=HTMLResponse)
async def get_dashboard_page():
    """통계 관리 페이지 반환"""
    html_path = Path(__file__).parent.parent.parent / "resources" / "html" / "dashboard.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/data.html", response_class=HTMLResponse)
async def get_data_page_html():
    """데이터 관리 페이지 반환 (data.html 직접 접근)"""
    html_path = Path(__file__).parent.parent.parent / "resources" / "html" / "data.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/users.html", response_class=HTMLResponse)
async def get_users_page():
    """사용자 관리 페이지 반환"""
    html_path = Path(__file__).parent.parent.parent / "resources" / "html" / "users.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# 정적 파일 서빙 (CSS, JS)
@router.get("/styles.css")
async def get_styles():
    """CSS 파일 반환"""
    css_path = Path(__file__).parent.parent.parent / "resources" / "html" / "styles.css"
    with open(css_path, "r", encoding="utf-8") as f:
        from fastapi.responses import Response
        return Response(content=f.read(), media_type="text/css")


@router.get("/api.js")
async def get_api_js():
    """API JavaScript 파일 반환"""
    js_path = Path(__file__).parent.parent.parent / "resources" / "html" / "api.js"
    with open(js_path, "r", encoding="utf-8") as f:
        from fastapi.responses import Response
        return Response(content=f.read(), media_type="application/javascript")


@router.get("/api/dashboard/tag-statistics/{category_type}")
async def get_tag_statistics(category_type: str):
    """
    카테고리 타입별 태그 통계 조회
    """
    data = await dashboard_service.get_tag_statistics(category_type)
    return JSONResponse(content=data)


@router.get("/api/dashboard/popular-places")
async def get_popular_places():
    """
    사용자 인기 장소 현황 조회
    """
    data = await dashboard_service.get_popular_places()
    return JSONResponse(content=data)

@router.get("/api/dashboard/district-stats")
async def get_district_stats():
    """
    서울특별시 자치구별 매장 수 통계 조회
    """
    data = await dashboard_service.get_district_stats()
    return JSONResponse(content=data)


@router.get("/api/dashboard/total-users")
async def get_total_users():
    """
    총 사용자 수 조회
    """
    data = await dashboard_data_service.get_total_users()
    return JSONResponse(content=data)


@router.get("/api/dashboard/recommendation-stats")
async def get_recommendation_stats():
    """
    일정표 생성 수 통계 조회
    """
    data = await dashboard_data_service.get_recommendation_stats()
    return JSONResponse(content=data)


@router.get("/api/dashboard/weekly-average-stats")
async def get_weekly_average_stats():
    """
    요일별 평균 일정표 생성 수 통계 조회
    """
    data = await dashboard_data_service.get_weekly_average_stats()
    return JSONResponse(content=data)


@router.get("/api/dashboard/popular-categories")
async def get_popular_categories():
    """
    인기 카테고리 통계 조회
    """
    data = await dashboard_data_service.get_popular_categories()
    return JSONResponse(content=data)


@router.get("/api/dashboard/popular-districts")
async def get_popular_districts():
    """
    일정표 생성 기준 인기 지역 통계 조회
    """
    data = await dashboard_data_service.get_popular_districts()
    return JSONResponse(content=data)


@router.get("/api/dashboard/template-stats")
async def get_template_stats():
    """
    일정 템플릿 통계 조회
    """
    data = await dashboard_data_service.get_template_stats()
    return JSONResponse(content=data)


@router.get("/api/dashboard/transportation-stats")
async def get_transportation_stats():
    """
    이동수단 통계 조회
    """
    data = await dashboard_data_service.get_transportation_stats()
    return JSONResponse(content=data)


@router.get("/api/dashboard/daily-travel-time-stats")
async def get_daily_travel_time_stats():
    """
    일별 평균 이동 시간 통계 조회
    """
    data = await dashboard_data_service.get_daily_travel_time_stats()
    return JSONResponse(content=data)


@router.get("/api/dashboard/total-travel-time-avg")
async def get_total_travel_time_avg():
    """
    전체 이동 평균 시간 조회
    """
    data = await dashboard_data_service.get_total_travel_time_avg()
    return JSONResponse(content=data)


@router.get("/api/dashboard/transportation-travel-time-avg")
async def get_transportation_travel_time_avg():
    """
    이동수단별 평균 이동 시간 조회
    """
    data = await dashboard_data_service.get_transportation_travel_time_avg()
    return JSONResponse(content=data)


@router.get("/api/dashboard/delete-cause-stats")
async def get_delete_cause_stats():
    """
    계정 삭제 이유 통계 조회
    """
    data = await dashboard_user_service.get_delete_cause_stats()
    return JSONResponse(content=data)


@router.get("/api/dashboard/general-inquiries")
async def get_general_inquiries():
    """
    일반 문의 사항 조회
    """
    data = await dashboard_user_service.get_general_inquiries()
    return JSONResponse(content=data)


@router.get("/api/dashboard/report-inquiries")
async def get_report_inquiries():
    """
    신고 문의 사항 조회
    """
    data = await dashboard_user_service.get_report_inquiries()
    return JSONResponse(content=data)


@router.get("/api/dashboard/account-and-report-status")
async def get_account_and_report_status():
    """
    계정 및 신고 현황 조회
    """
    data = await dashboard_user_service.get_account_and_report_status()
    return JSONResponse(content=data)