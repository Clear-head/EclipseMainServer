from fastapi import APIRouter

from src.logger.custom_logger import get_logger

router = APIRouter(prefix="/admin", tags=["users"])
logger = get_logger(__name__)


@router.get("/monitoring")
async def monitoring():
    pass