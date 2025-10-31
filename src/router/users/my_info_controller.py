from fastapi import APIRouter, Request, Depends
from starlette.responses import JSONResponse

from src.domain.dto.service.change_nickname_dto import RequestChangeNicknameDto
from src.domain.dto.service.user_like_dto import RequestGetUserLikeDTO, RequestSetUserLikeDTO
from src.logger.custom_logger import get_logger
from src.service.application.my_info_service import UserInfoService
from src.service.auth.jwt import validate_jwt_token

router = APIRouter(
    prefix="/api/service",
    dependencies=[Depends(validate_jwt_token)]
)
logger = get_logger(__name__)

user_info = UserInfoService()


@router.post("/set-my-like")
async def set_my_like(dto: RequestSetUserLikeDTO):
    return JSONResponse(status_code=200, content=await user_info.set_my_like(dto, True))


@router.delete("/set-my-like")
async def set_my_like(dto: RequestSetUserLikeDTO):
    return JSONResponse(status_code=200, content=await user_info.set_my_like(dto, False))


@router.post("/get-my-like")
async def my_like(request_data: RequestGetUserLikeDTO) -> JSONResponse:
    like_list = await user_info.get_user_like(request_data.user_id)
    return JSONResponse(content=like_list.model_dump())

@router.get("/my-review")
async def my_review(request: Request) -> JSONResponse:
    pass


@router.post("/my-history")
async def my_history(request: Request) -> JSONResponse:


    # request_data = RequestUserLikeDTO(user_id=request.user.id)
    # content = await user_info.get_user_review(request_data.user_id)
    #
    # return JSONResponse(content=content.model_dump())
    pass


@router.put("/change-nickname")
async def change_nickname(dto: RequestChangeNicknameDto):
    content = await user_info.change_nickname(dto)

    return JSONResponse(status_code=200, content=content.model_dump())