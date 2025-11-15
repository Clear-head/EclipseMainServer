from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from src.domain.dto.user.user_account_dto import RequestDeleteAccountDTO
from src.domain.dto.user.user_profile_dto import RequestUpdateProfileDTO
from src.logger.custom_logger import get_logger
from src.router.users.auth_controller import user_service
from src.router.users.my_info_controller import user_info
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(prefix="/api/users", tags=["users"])
logger = get_logger(__name__)


@router.put("/me/{field}")
async def change_info(field: str, dto: RequestUpdateProfileDTO, user_id:str = Depends(get_jwt_user_id)):
    return await user_info.change_info(dto, field, user_id)


#   회원탈퇴
@router.delete('/me')
async def delete_account(dto: RequestDeleteAccountDTO, user_id:str = Depends(get_jwt_user_id)):
    await user_service.delete_account(user_id, dto)
    return JSONResponse(status_code=200, content={"status": "success"})

