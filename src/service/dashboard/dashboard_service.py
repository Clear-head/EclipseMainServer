from datetime import datetime

from src.infra.database.repository.statistics_repository import StatisticsRepository
from src.logger.custom_logger import get_logger


class DashboardService:
    def __init__(self):
        self.logger = get_logger(__name__)

    #   총 유저 수
    async def get_user_count(self) -> int:
        """
        총 유저 수를 조회합니다.
        
        Returns:
            int: 총 유저 수
        """
        try:
            self.logger.info("총 유저 수를 조회")
            return await StatisticsRepository().get_user_count()
        except Exception as e:
            self.logger.error(f"총 유저 수 조회 오류: {e}")
            raise e

    #   날짜별 템플릿 작성 수
    async def get_history_count(self, visited_at: datetime = None) -> list:
        """
        날짜별 템플릿 작성 수를 조회합니다.
        
        Args:
            visited_at: 조회할 날짜 (None이면 전체)
        
        Returns:
            list: 조회된 히스토리 리스트
        """
        try:
            self.logger.info("날짜별 템플릿 작성 수를 조회")
            return await StatisticsRepository().get_history_count(visited_at)
        except Exception as e:
            self.logger.error(f"날짜별 템플릿 작성 수 조회 오류: {e}")
            raise e

    async def get_tag_statistics(self, category_type: str) -> list:
        """
        카테고리 타입별 태그 통계를 조회합니다.
        
        Args:
            category_type: 카테고리 타입 ('0', '1', '2')
        
        Returns:
            list: [{'name': '태그명', 'total_count': 123}, ...]
        """
        try:
            self.logger.info(f"카테고리 타입별 태그 통계를 조회: {category_type}")
            if category_type not in ['0', '1', '2']:
                raise Exception('Invalid category_type')
            return await StatisticsRepository().get_tag_statistics(category_type)
        except Exception as e:
            self.logger.error(f"태그 통계 조회 오류: {e}")
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
            self.logger.error(f"인기 장소 조회 오류: {e}")
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




