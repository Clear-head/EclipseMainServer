import traceback

from fastapi import APIRouter
from src.domain.dto.service.main_screen_dto import RequestMainScreenDTO
from src.domain.dto.service.request_jwt_dto import RequestAccessTokenDto
from src.logger.custom_logger import get_logger
from src.service.application.main_screen_service import MainScreenService
from src.service.auth.jwt import validate_jwt_token
from src.utils.exception_handler.auth_error_class import MissingTokenException, ExpiredAccessTokenException, \
    ExpiredRefreshTokenException

router = APIRouter(prefix="/api/service")
logger = get_logger(__name__)


#   메인 화면: 로그인 후 바로 보여지는 화면
@router.post("/main")
@router.get("/main")
async def to_main_screen(dto: RequestMainScreenDTO):
    jwt = dto.headers.jwt

    if jwt is None:
        logger.error("Missing token")
        raise MissingTokenException()

    validate_result = await validate_jwt_token(jwt)

    if validate_result == 2:
        logger.error("ExpiredToken token")
        raise ExpiredAccessTokenException()

    main_service_class = MainScreenService()
    return await main_service_class.to_main()