from fastapi import APIRouter
from starlette.responses import RedirectResponse

from src.domain.dto.user.user_sanctions_dto import RequestUserSanctionsDTO
from src.logger.custom_logger import get_logger
from src.service.sanctions.sanction_service import SanctionService

router = APIRouter(prefix="/admin", tags=["users"])
logger = get_logger(__name__)


@router.get("/monitoring")
async def monitoring():
    pass


@router.post("/sanctions")
async def sanctions_user(dto: RequestUserSanctionsDTO):
    if await SanctionService().add_ban_user(dto):
        return RedirectResponse(url="/monitoring")
    else:
        return RedirectResponse(url="/monitoring", status_code=500)