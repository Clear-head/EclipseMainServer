from datetime import datetime

from src.infra.database.repository.merge_history_repository import MergeHistoryRepository
from src.infra.database.repository.statistics_repository import StatisticsRepository
from src.infra.database.repository.user_history_repository import UserHistoryRepository
from src.infra.database.repository.users_repository import UserRepository
from src.logger.custom_logger import get_logger


class DashboardService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.user_repo = UserRepository()
        self.merge_history_repo = MergeHistoryRepository()
        self.user_history_repo = UserHistoryRepository()

    #   총 유저 수
    async def get_user_count(self) -> int:
        return len(await self.user_repo.select(columns=['id']))

    #   날짜별 템플릿 작성 수
    async def get_history_count(self, visited_at: datetime = None):
        if visited_at is None:
            await self.user_history_repo.select(columns=['id'])
        else:
            await self.user_history_repo.select(columns=['id'], visited_at=visited_at)

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




