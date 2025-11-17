from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from src.domain.dto.category.category_detail_dto import ResponseCategoryDetailDTO
from src.domain.dto.category.category_dto import ResponseCategoryListDTO
from src.logger.custom_logger import get_logger
from src.service.auth.jwt import get_jwt_user_id
from src.service.category.category_service import MainScreenService
from src.service.user.history_service import HistoryService

router = APIRouter(
    prefix="/api/categories"
)
logger = get_logger(__name__)
main_service_class = MainScreenService()
@router.get("/")
async def to_main_screen(user_id: str = Depends(get_jwt_user_id)) -> ResponseCategoryListDTO:
    return await main_service_class.to_main()

@router.get("/{category_id}")
async def to_detail(category_id: str, user_id: str = Depends(get_jwt_user_id)) -> ResponseCategoryDetailDTO:
    return await main_service_class.get_category_detail(category_id, user_id)

@router.get("/today-recommendations")
async def what_to_do_screen(user_id: str = Depends(get_jwt_user_id)):
    return JSONResponse(
        content=[
            await HistoryService().get_user_history_list(user_id, 1),
            await main_service_class.to_main(1)
        ]
    )
