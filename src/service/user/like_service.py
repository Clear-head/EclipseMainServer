from src.domain.dto.like.like_dto import ResponseLikeListDTO, RequestToggleLikeDTO
from src.domain.entities.user_like_entity import UserLikeEntity
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.user_like_repository import UserLikeRepository
from src.logger.custom_logger import get_logger


class LikeService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.repo = UserLikeRepository()

    #   좋아요 설정
    async def set_my_like(self, data: RequestToggleLikeDTO, type: bool, user_id: str) -> str:
        self.logger.info(f"try {user_id} set my like: {type}")

        if not type:
            flag = await self.repo.delete(user_id=user_id, category_id=data.category_id)
        else:
            flag = await self.repo.insert(
                UserLikeEntity(
                    user_id=user_id,
                    category_id=data.category_id
                )
            )

        if not flag:
            self.logger.error(f"찜 목록 설정 실패 user: {user_id}, category: {data.category_id}")
            raise Exception(f"찜 목록 설정 실패 user: {user_id}, category: {data.category_id}")

        else:
            return "success"

    #   좋아요 목록 조회
    async def get_user_like(self, user_id) -> ResponseLikeListDTO:
        self.logger.info(f"try {user_id} get user like: {user_id}")

        liked = await self.repo.select(user_id=user_id)

        if not liked:
            self.logger.info(f"no like for {user_id}")
            return ResponseLikeListDTO(
                like_list=[]
            )

        else:
            ans = await CategoryRepository().get_review_statistics(
                id=[i.category_id for i in liked],
                is_random=False
            )
            return ResponseLikeListDTO(
                like_list=ans
            )