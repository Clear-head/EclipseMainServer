from src.infra.database.repository.statistics_repository import StatisticsRepository
from src.logger.custom_logger import get_logger


class DashboardDataService:
    def __init__(self):
        self.logger = get_logger(__name__)


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

    async def get_daily_travel_time_stats(self) -> list:
        """
        일별 평균 이동 시간 통계를 조회합니다.
        
        Returns:
            list: [{'date': '2024-01-01', 'avg_duration': 42.5, 'weekly_diff': 3.2}, ...]
        """
        try:
            self.logger.info("일별 평균 이동 시간 통계를 조회")
            return await StatisticsRepository().get_daily_travel_time_stats()
        except Exception as e:
            self.logger.error(f"일별 평균 이동 시간 통계 조회 오류: {e}")
            raise e

    async def get_total_travel_time_avg(self) -> dict:
        """
        전체 이동 평균 시간을 조회합니다.
        
        Returns:
            dict: {'avg_duration': 42.5}
        """
        try:
            self.logger.info("전체 이동 평균 시간을 조회")
            return await StatisticsRepository().get_total_travel_time_avg()
        except Exception as e:
            self.logger.error(f"전체 이동 평균 시간 조회 오류: {e}")
            raise e

    async def get_transportation_travel_time_avg(self) -> list:
        """
        이동수단별 평균 이동 시간을 조회합니다.
        
        Returns:
            list: [{'transportation': '0', 'type_name': '도보', 'avg_minutes': 3.2}, ...]
        """
        try:
            self.logger.info("이동수단별 평균 이동 시간을 조회")
            return await StatisticsRepository().get_transportation_travel_time_avg()
        except Exception as e:
            self.logger.error(f"이동수단별 평균 이동 시간 조회 오류: {e}")
            raise e


