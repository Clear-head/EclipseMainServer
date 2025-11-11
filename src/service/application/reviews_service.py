from datetime import datetime

from src.domain.dto.service.reviews_dto import RequestSetReviewsDto
from src.domain.dto.service.user_reivew_dto import ResponseUserReviewDTO, UserReviewDTO
from src.domain.entities.reviews_entity import ReviewsEntity
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.tables.table_category import category_table
from src.logger.custom_logger import get_logger
from src.utils.uuid_maker import generate_uuid


class ReviewsService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.repo = ReviewsRepository()


    #   리뷰 쓰기
    async def set_user_review(self, user_id:str, dto: RequestSetReviewsDto):
        try:
            self.logger.info(f"try {user_id} set user reivew: {dto}")
            await self.repo.insert(ReviewsEntity(
                user_id=user_id,
                category_id=dto.category_id,
                id=generate_uuid(),
                stars=dto.stars,
                comments=dto.comments,
                created_at=datetime.now(),
            ))

            return "success"

        except Exception as e:
            self.logger.error(e)
            raise e


    #   리뷰 리스트 조회
    async def get_user_reviews(self, user_id) -> ResponseUserReviewDTO:
        self.logger.info(f"try {user_id} get user review: {user_id}")
        result = await self.repo.select(
            return_dto=UserReviewDTO,
            joins=[
                {
                    "table": category_table,
                    "on": {"category_id": "id"},
                    "alias": "category"
                }
            ],
            columns={
                "id": "review_id",
                "comment": "comment",
                "stars": "stars",
                "category.name": "category_name",
                "created_at": "created_at"
            },
            user_id=user_id,
        )

        return ResponseUserReviewDTO(
            review_list=result
        )