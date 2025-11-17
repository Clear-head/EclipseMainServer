from fastapi import APIRouter, Depends, Header
from starlette.responses import JSONResponse

from src.domain.dto.user.user_account_dto import RequestDeleteAccountDTO
from src.domain.dto.user.user_profile_dto import RequestUpdateProfileDTO
from src.logger.custom_logger import get_logger
from src.service.user.user_service import UserService
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(prefix="/api/users", tags=["users"])
logger = get_logger(__name__)

user_service = UserService()


@router.put("/me/{field}")
async def change_info(field: str, dto: RequestUpdateProfileDTO, user_id: str = Depends(get_jwt_user_id)):
    return await user_service.change_info(dto, field, user_id)


@router.delete('/me')
async def delete_account(
        dto: RequestDeleteAccountDTO,
        jwt: str = Header(None),
        user_id: str = Depends(get_jwt_user_id)
):
    await user_service.delete_account(user_id, dto, jwt)
    return JSONResponse(status_code=200, content={"status": "success"})