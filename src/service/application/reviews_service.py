from datetime import datetime

from src.domain.dto.review.review_dto import RequestCreateReviewDTO, ReviewDTO, ResponseReviewListDTO, \
    ResponseReviewCountDTO, ResponseDeleteReviewDTO
from src.domain.entities.reviews_entity import ReviewsEntity
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.tables.table_category import category_table
from src.logger.custom_logger import get_logger
from src.utils.exception_handler.service_error_class import NotFoundAnyItemException
from src.utils.uuid_maker import generate_uuid


class ReviewsService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.repo = ReviewsRepository()


    #   리뷰 쓰기
    async def set_user_review(self, user_id:str, dto: RequestCreateReviewDTO):
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
    async def get_user_reviews(self, user_id)-> ResponseReviewListDTO:
        self.logger.info(f"try {user_id} get user review: {user_id}")
        result = await self.repo.select(
            return_dto=ReviewDTO,
            joins=[
                {
                    "table": category_table,
                    "on": {"category_id": "id"},
                    "alias": "category"
                }
            ],
            columns={
                "id": "review_id",
                "comments": "comment",
                "stars": "stars",
                "category.id": "category_id",
                "category.type": "category_type",
                "category.name": "category_name",
                "created_at": "created_at"
            },
            user_id=user_id,
        )

        sorted_result = sorted(result, key=lambda x: x.created_at, reverse=True)
        
        return ResponseReviewListDTO(
            review_list=sorted_result
        )

    #   리뷰 삭제
    async def delete_user_review(self, user_id: str, review_id: str) -> ResponseDeleteReviewDTO:
        try:
            self.logger.info(f"try {user_id} delete review: {review_id}")

            review = await self.repo.select(id=review_id, user_id=user_id)

            if not review:
                raise NotFoundAnyItemException()

            await self.repo.delete(id=review_id, user_id=user_id)

            return ResponseDeleteReviewDTO(
                message="리뷰가 삭제되었습니다.",
                review_id=review_id
            )

        except Exception as e:
            self.logger.error(e)
            raise e


    # 🔥 추가: 특정 카테고리에 작성한 리뷰 개수 조회
    async def get_user_review_count(self, user_id: str, category_id: str) -> ResponseReviewCountDTO:
        """
        특정 사용자가 특정 카테고리(매장)에 작성한 리뷰 개수를 조회합니다.
        
        Args:
            user_id: 사용자 ID
            category_id: 카테고리(매장) ID
            
        Returns:
            int: 해당 매장에 작성한 리뷰 개수
        """
        try:
            self.logger.info(f"try get review count for user: {user_id}, category: {category_id}")
            
            # user_id와 category_id가 일치하는 리뷰 조회
            reviews = await self.repo.select(
                user_id=user_id,
                category_id=category_id
            )
            
            count = len(reviews) if reviews else 0
            
            self.logger.info(f"user {user_id} has {count} reviews for category {category_id}")
            
            return ResponseReviewCountDTO(review_count=count)
            
        except Exception as e:
            self.logger.error(f"Error getting review count: {e}")
            # 오류 발생 시 0 반환 (안전한 기본값)
            return ResponseReviewCountDTO(review_count=0)