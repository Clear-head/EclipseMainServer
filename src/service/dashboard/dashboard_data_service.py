from sqlalchemy import text
from src.infra.database.repository.maria_engine import get_engine
from src.infra.database.repository.statistics_repository import StatisticsRepository
from src.logger.custom_logger import get_logger


class DashboardDataService:
    def __init__(self):
        self.logger = get_logger(__name__)

    async def get_tag_statistics(self, category_type: str) -> list:
        try:
            self.logger.info("")
            if category_type not in ['0', '1', '2']:
                raise Exception('Invalid category_type')
            return await StatisticsRepository().get_tag_statistics(category_type)
        except Exception as e:
            self.logger.error(e)
            raise e

    async def get_popular_places(self) -> list:
        """
        사용자 인기 장소 현황을 조회합니다.
        
        Returns:
            list: [{'이름': '장소명', '구': '강남구', '서브카테고리': '한식', '메뉴': '...'}, ...]
        """
        try:
            self.logger.info("사용자 인기 장소 현황을 조회")
            return await StatisticsRepository().get_popular_places()
        except Exception as e:
            self.logger.error(e)
            raise e


    async def get_district_stats(self) -> list:
        """
        서울특별시 자치구별 매장 수 통계를 조회합니다.
        
        Returns:
            list: [{'gu': '강남구', '음식점': 268, '카페': 124, '콘텐츠': 86}, ...]
        """
        try:
            self.logger.info("서울특별시 자치구별 매장 수 통계를 조회")
            return await StatisticsRepository().get_district_stats()
        except Exception as e:
            self.logger.error(f"구별 통계 조회 오류: {e}")
            raise e

    async def get_total_users(self) -> dict:
        """
        총 사용자 수를 조회합니다.
        
        Returns:
            dict: {'total_users': 12345}
        """
        try:
            self.logger.info("총 사용자 수를 조회")
            return await StatisticsRepository().get_total_users()
        except Exception as e:
            self.logger.error(f"총 사용자 수 조회 오류: {e}")
            raise e

    async def get_recommendation_stats(self) -> list:
        """
        일정표 생성 수 통계를 조회합니다.
        
        Returns:
            list: [{'visited_date': '2024-01-01', 'count': 482}, ...]
        """
        try:
            self.logger.info("일정표 생성 수 통계를 조회")
            return await StatisticsRepository().get_recommendation_stats()
        except Exception as e:
            self.logger.error(f"일정표 생성 수 통계 조회 오류: {e}")
            raise e

    async def get_weekly_average_stats(self) -> list:
        """
        요일별 평균 일정표 생성 수 통계를 조회합니다.
        
        Returns:
            list: [{'weekday_kor': '월', 'avg_per_week': 68}, ...]
        """
        try:
            self.logger.info("요일별 평균 일정표 생성 수 통계를 조회")
            return await StatisticsRepository().get_weekly_average_stats()
        except Exception as e:
            self.logger.error(f"요일별 평균 일정표 생성 수 통계 조회 오류: {e}")
            raise e

    async def get_popular_categories(self) -> list:
        """
        인기 카테고리 통계를 조회합니다.
        
        Returns:
            list: [{'category_type': '0', 'total_count': 100, 'percentage': 55.0}, ...]
        """
        try:
            self.logger.info("인기 카테고리 통계를 조회")
            return await StatisticsRepository().get_popular_categories()
        except Exception as e:
            self.logger.error(f"인기 카테고리 통계 조회 오류: {e}")
            raise e

    async def get_popular_districts(self) -> list:
        """
        일정표 생성 기준 인기 지역 통계를 조회합니다.
        
        Returns:
            list: [{'district': '강남구', 'total_count': 142}, ...]
        """
        try:
            self.logger.info("일정표 생성 기준 인기 지역 통계를 조회")
            return await StatisticsRepository().get_popular_districts()
        except Exception as e:
            self.logger.error(f"인기 지역 통계 조회 오류: {e}")
            raise e

    async def get_template_stats(self) -> list:
        """
        일정 템플릿 통계를 조회합니다.
        
        Returns:
            list: [{'template_type': '1', 'total_count': 100, 'percentage': 52.0}, ...]
        """
        try:
            self.logger.info("일정 템플릿 통계를 조회")
            return await StatisticsRepository().get_template_stats()
        except Exception as e:
            self.logger.error(f"일정 템플릿 통계 조회 오류: {e}")
            raise e

    async def get_transportation_stats(self) -> list:
        """
        이동수단 통계를 조회합니다.
        
        Returns:
            list: [{'transportation': '도보', 'total_count': 100, 'percentage': 40.0}, ...]
        """
        try:
            self.logger.info("이동수단 통계를 조회")
            return await StatisticsRepository().get_transportation_stats()
        except Exception as e:
            self.logger.error(f"이동수단 통계 조회 오류: {e}")
            raise e

