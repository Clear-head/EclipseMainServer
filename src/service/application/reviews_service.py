from datetime import datetime

from fastapi import HTTPException # 삭제 기능 때매 추가

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
                "comments": "comment", # 오타인듯?
                "stars": "stars",
                "category_id": "category_id", # my_review_screen에 필요
                "category.name": "category_name",
                "category.type": "category_type", # my_review_screen에 필요
                "created_at": "created_at"
            },
            user_id=user_id,
        )

        return ResponseUserReviewDTO(
            review_list=result
        )

    #   리뷰 삭제 # 삭제 기능 때매 추가
    async def delete_user_review(self, user_id: str, review_id: str) -> dict:
        try:
            self.logger.info(f"try {user_id} delete review: {review_id}")

            review = await self.repo.select(id=review_id, user_id=user_id)

            if not review:
                raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다.")

            await self.repo.delete(id=review_id, user_id=user_id)

            return {
                "message": "리뷰가 삭제되었습니다.",
                "review_id": review_id
            }

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(e)
            raise e