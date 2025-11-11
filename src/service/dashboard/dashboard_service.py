from datetime import datetime

from src.infra.database.repository.merge_history_repository import MergeHistoryRepository
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




