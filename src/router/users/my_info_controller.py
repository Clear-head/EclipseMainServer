from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from src.domain.dto.service.reviews_dto import RequestSetReviewsDto
from src.domain.dto.service.user_like_dto import RequestSetUserLikeDTO
from src.logger.custom_logger import get_logger
from src.service.application.my_info_service import UserInfoService
from src.service.application.reviews_service import ReviewsService
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(
    prefix="/api/users/me"
)
logger = get_logger(__name__)

user_info = UserInfoService()


#   좋아요 조회
@router.get("/likes")
async def my_like(user_id:str = Depends(get_jwt_user_id)) -> JSONResponse:
    like_list = await user_info.get_user_like(user_id)
    return JSONResponse(content=like_list.model_dump())


#   좋아요 설정
@router.post("/likes")
async def set_like(dto: RequestSetUserLikeDTO, user_id:str = Depends(get_jwt_user_id)):
    return JSONResponse(status_code=200, content=await user_info.set_my_like(dto, True, user_id))


#   좋아요 취소
@router.delete("/likes")
async def delete_like(dto: RequestSetUserLikeDTO, user_id:str = Depends(get_jwt_user_id)):
    return JSONResponse(status_code=200, content=await user_info.set_my_like(dto, False, user_id=user_id))



#   히스토리 목록 조회
@router.get("/histories")
async def get_history_list(user_id:str = Depends(get_jwt_user_id)):
    return await user_info.get_user_history_list(user_id)


#   히스토리 상세 조회
@router.get("/histories/detail/{merge_history_id}")
async def get_history_detail(merge_history_id:str, user_id:str = Depends(get_jwt_user_id)):
    return await user_info.get_user_history_detail(user_id, merge_history_id)


# 🔥 추가: 특정 카테고리 방문 횟수 조회
@router.get("/histories/visit-count/{category_id}")
async def get_visit_count(category_id: str, user_id: str = Depends(get_jwt_user_id)):
    """
    특정 카테고리(매장)에 방문한 횟수를 조회합니다.
    """
    count = await user_info.get_category_visit_count(user_id, category_id)
    return JSONResponse(content={"visit_count": count})



#   리뷰 리스트 조회
@router.get("/reviews")
async def get_review(user_id:str = Depends(get_jwt_user_id)):
    return await ReviewsService().get_user_reviews(user_id)


# 🔥 추가: 특정 카테고리에 작성한 리뷰 개수 조회
@router.get("/reviews/count/{category_id}")
async def get_review_count(category_id: str, user_id: str = Depends(get_jwt_user_id)):
    """
    특정 카테고리(매장)에 작성한 리뷰 개수를 조회합니다.
    """
    count = await ReviewsService().get_user_review_count(user_id, category_id)
    return JSONResponse(content={"review_count": count})


#   리뷰 쓰기
@router.post("/reviews")
async def set_reviews(dto: RequestSetReviewsDto, user_id:str = Depends(get_jwt_user_id)):
    return JSONResponse(content=await ReviewsService().set_user_review(user_id, dto))


#   리뷰 삭제
@router.delete("/reviews/{review_id}")
async def delete_review(review_id: str, user_id: str = Depends(get_jwt_user_id)):
    result = await ReviewsService().delete_user_review(user_id, review_id)
    return JSONResponse(status_code=200, content=result)