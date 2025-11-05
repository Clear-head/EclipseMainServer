from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from src.logger.custom_logger import get_logger
from src.service.application.main_screen_service import MainScreenService
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(
    prefix="/api/categories"
)
logger = get_logger(__name__)

@router.get("/")
async def to_main_screen(user_id: str = Depends(get_jwt_user_id)):
    main_service_class = MainScreenService()

    content = await main_service_class.to_main()
    return JSONResponse(
        content=content.model_dump()
    )

@router.get("/{category_id}")
async def to_detail(category_id: str, user_id: str = Depends(get_jwt_user_id)):

    main_service_class = MainScreenService()
    content = await main_service_class.get_category_detail(category_id)
    return JSONResponse(
        content=content.model_dump()
    )
