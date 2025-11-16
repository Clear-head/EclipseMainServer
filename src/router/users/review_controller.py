from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from src.domain.dto.review.review_dto import RequestCreateReviewDTO, ResponseDeleteReviewDTO, ResponseReviewListDTO
from src.logger.custom_logger import get_logger
from src.service.user.reviews_service import ReviewsService
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(
    prefix="/api/users/me"
)
logger = get_logger(__name__)

user_info = ReviewsService()

# 리뷰 작성 가능한 매장 목록 조회
@router.get("/reviews/reviewable")
async def get_reviewable_stores(
    limit: int = 6,
    user_id: str = Depends(get_jwt_user_id)
) -> ResponseReviewListDTO:
    """
    리뷰 작성 가능한 매장 목록을 조회합니다.
    (방문 횟수 > 리뷰 개수인 매장만 반환, 최신 방문순, 최대 6개)
    """
    return await user_info.get_reviewable_stores(user_id, limit)


# 리뷰 리스트 조회
@router.get("/reviews")
async def get_review(user_id: str = Depends(get_jwt_user_id)) -> ResponseReviewListDTO:
    return await ReviewsService().get_user_reviews(user_id)


# 특정 카테고리에 작성한 리뷰 개수 조회
@router.get("/reviews/count/{category_id}")
async def get_review_count(category_id: str, user_id: str = Depends(get_jwt_user_id)):
    """
    특정 카테고리(매장)에 작성한 리뷰 개수를 조회합니다.
    """
    return await ReviewsService().get_user_review_count(user_id, category_id)


# 리뷰 쓰기
@router.post("/reviews")
async def set_reviews(dto: RequestCreateReviewDTO, user_id: str = Depends(get_jwt_user_id)):
    return JSONResponse(content=await ReviewsService().set_user_review(user_id, dto))


# 리뷰 삭제
@router.delete("/reviews/{review_id}")
async def delete_review(review_id: str, user_id: str = Depends(get_jwt_user_id)) -> ResponseDeleteReviewDTO:
    return await ReviewsService().delete_user_review(user_id, review_id)