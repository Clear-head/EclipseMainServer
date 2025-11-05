from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse
from urllib3.fields import RequestField

from src.domain.dto.service.change_info_dto import RequestChangeInfoDto
from src.domain.dto.service.user_delete_account_dto import RequestDeleteAccount
from src.logger.custom_logger import get_logger
from src.router.users.auth_controller import user_service
from src.router.users.my_info_controller import user_info
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(prefix="/api/users", tags=["users"])
logger = get_logger(__name__)


@router.put("/me/{field}")
async def change_info(field: str, dto: RequestChangeInfoDto, user_id:str = Depends(get_jwt_user_id)):
    return JSONResponse(status_code=200, content=(await user_info.change_info(dto, field, user_id)).model_dump())


#   회원탈퇴
@router.delete('/me')
async def delete_account(dto: RequestDeleteAccount, user_id:str = Depends(get_jwt_user_id)):
    await user_service.delete_account(user_id, dto.password)
    return JSONResponse(status_code=200, content={"status": "success"})

