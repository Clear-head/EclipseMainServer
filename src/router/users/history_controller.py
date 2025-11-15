from fastapi import APIRouter, Depends

from src.domain.dto.history.history_dto import ResponseHistoryListDTO, ResponseHistoryDetailDTO
from src.logger.custom_logger import get_logger
from src.service.application.my_info_service import UserInfoService
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(
    prefix="/api/users/me"
)
logger = get_logger(__name__)

user_info = UserInfoService()

# 히스토리 목록 조회
@router.get("/histories")
async def get_history_list(user_id: str = Depends(get_jwt_user_id)) -> ResponseHistoryListDTO:
    return await user_info.get_user_history_list(user_id)


# 글쓸 때 히스토리 조회 (10개 제한)
@router.get("/histories/post")
async def get_history_list(user_id: str = Depends(get_jwt_user_id)) -> ResponseHistoryListDTO:
    return await user_info.get_user_history_list(user_id, True)


# 히스토리 상세 조회
@router.get("/histories/detail/{merge_history_id}")
async def get_history_detail(merge_history_id: str, user_id: str = Depends(get_jwt_user_id)) -> ResponseHistoryDetailDTO:
    return await user_info.get_user_history_detail(user_id, merge_history_id)


# 특정 카테고리 방문 횟수 조회
@router.get("/histories/visit-count/{category_id}")
async def get_visit_count(category_id: str, user_id: str = Depends(get_jwt_user_id)):
    """
    특정 카테고리(매장)에 방문한 횟수를 조회합니다.
    """
    return await user_info.get_category_visit_count(user_id, category_id)