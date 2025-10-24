import traceback

from fastapi import APIRouter
from src.domain.dto.service.main_screen_dto import RequestMainScreenDTO
from src.domain.dto.service.request_jwt_dto import RequestAccessTokenDto
from src.logger.custom_logger import get_logger
from src.service.application.main_service import MainService
from src.service.auth.jwt import validate_jwt_token
from src.utils.exception_handler.auth_error_class import MissingTokenException, ExpiredAccessTokenException, \
    ExpiredRefreshTokenException

router = APIRouter(prefix="/api/service")
logger = get_logger(__name__)



@router.post("/main")
@router.get("/main")
async def to_main_screen(dto: RequestMainScreenDTO):
    jwt = dto.headers.jwt

    if jwt is None:
        logger.error("Missing token")
        raise MissingTokenException()

    validate_result = await validate_jwt_token(jwt)

    if validate_result is 2:
        logger.error("ExpiredToken token")
        raise ExpiredAccessTokenException()

    main_service_class = MainService()
    return await main_service_class.to_main()


@router.get("/refresh")
async def to_refresh(dto: RequestAccessTokenDto):
    jwt = dto.header.jwt

    if jwt is None:
        logger.error("Missing token")
        raise MissingTokenException()

    validate_result = await validate_jwt_token(jwt)
    if validate_result is 2:
        #   todo: 세션에서 삭제
        #       로그아웃 까지
        raise ExpiredRefreshTokenException()