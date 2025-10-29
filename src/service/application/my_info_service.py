from src.infra.database.repository.user_like_repository import UserLikeRepository
from src.infra.database.repository.users_repository import UserRepository
from src.logger.custom_logger import get_logger


class UserInfoService:
    def __init__(self):
        self.logger = get_logger(__name__)

    async def get_my_like(self, user_id):
        user_like_repo = UserLikeRepository()
        liked = await user_like_repo.select_by(user_id=user_id)

        if not liked:
            self.logger.info(f"no like for {user_id}")

        return liked
