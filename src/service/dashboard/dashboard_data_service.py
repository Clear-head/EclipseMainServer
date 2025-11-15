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

