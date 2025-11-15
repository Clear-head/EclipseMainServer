from datetime import datetime

from src.domain.dto.user.user_sanctions_dto import RequestUserSanctionsDTO
from src.domain.entities.black_entity import BlackEntity
from src.infra.database.repository.black_repository import BlackRepository
from src.logger.custom_logger import get_logger


class SanctionService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.black_repo = BlackRepository()


    async def add_ban_user(self, dto: RequestUserSanctionsDTO):
        try:
            self.logger.info(f"Adding user {dto.user_id} to black list")
            await self.black_repo.insert(
                BlackEntity(
                    user_id=dto.user_id,
                    sanction=dto.sanction,
                    started_at=datetime.now(),
                    finished_at=dto.finished_at,
                    email=dto.email,
                    phone=dto.phone
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to add user {dto.user_id} to black list: {e}")
            raise e

        return True