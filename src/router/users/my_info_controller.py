from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from src.domain.dto.service.user_like_dto import RequestUserLikeDTO, ResponseUserLikeDTO
from src.logger.custom_logger import get_logger
from src.service.application.my_info_service import UserInfoService

router = APIRouter(prefix="/api/service")
logger = get_logger(__name__)


@router.get("/my-like")
async def my_like(request: Request) -> JSONResponse:
    # jwt = request.headers.get("jwt")
    #
    # if jwt is None:
    #     logger.error("Missing token")
    #     raise MissingTokenException()
    #
    # validate_result = await validate_jwt_token(jwt)
    #
    # if validate_result == 2:
    #     logger.error("Expired token")
    #     raise ExpiredAccessTokenException()


    user_info = UserInfoService()

    request_data = RequestUserLikeDTO(user_id=request.user.id)
    like_list = await user_info.get_my_like(request_data.user_id)
    content = ResponseUserLikeDTO(like_list=like_list)

    return JSONResponse(content=content.model_dump())
