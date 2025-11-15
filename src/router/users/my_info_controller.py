from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from src.domain.dto.history.history_dto import ResponseHistoryListDTO, ResponseHistoryDetailDTO
from src.domain.dto.like.like_dto import ResponseLikeListDTO, RequestToggleLikeDTO
from src.domain.dto.review.review_dto import ResponseReviewListDTO, RequestCreateReviewDTO, ResponseDeleteReviewDTO
from src.logger.custom_logger import get_logger
from src.service.application.my_info_service import UserInfoService
from src.service.application.reviews_service import ReviewsService
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(
    prefix="/api/users/me"
)
logger = get_logger(__name__)

user_info = UserInfoService()


# 좋아요 조회
@router.get("/likes")
async def my_like(user_id: str = Depends(get_jwt_user_id)) -> ResponseLikeListDTO:
    return await user_info.get_user_like(user_id)


# 좋아요 설정
@router.post("/likes")
async def set_like(dto: RequestToggleLikeDTO, user_id: str = Depends(get_jwt_user_id)):
    return JSONResponse(status_code=200, content=await user_info.set_my_like(dto, True, user_id))


# 좋아요 취소
@router.delete("/likes")
async def delete_like(dto: RequestToggleLikeDTO, user_id: str = Depends(get_jwt_user_id)):
    return JSONResponse(status_code=200, content=await user_info.set_my_like(dto, False, user_id=user_id))