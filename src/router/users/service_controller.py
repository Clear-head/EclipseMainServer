from fastapi import APIRouter

from src.domain.dto.header import JsonHeader
from src.domain.dto.service.error_response import ErrorResponseDto, ErrorResponseBody
from src.domain.dto.service.main_screen_dto import RequestMainScreenDTO
from src.logger.logger_handler import get_logger
from src.service.application.main_service import MainService
from src.service.auth.jwt import validate_jwt_token

router = APIRouter(prefix="/api/service")
logger = get_logger(__name__)



@router.post("/main")
@router.get("/main")
async def to_main_screen(dto: RequestMainScreenDTO):

    jwt = dto.headers.jwt
    print(await validate_jwt_token(jwt))
    main_service_class = MainService()
    return await main_service_class.to_main()


    # try:
    #     jwt = dto.headers.jwt
    #     print(jwt)
    #
    #     if jwt is None:
    #         logger.error("Invalid token")
    #         raise Exception('Invalid token')
    #
    #     elif await validate_jwt_token(jwt) != 1:
    #         raise Exception('JWT validation error')
    #
    #     else:
    #         main_service_class = MainService()
    #         return await main_service_class.to_main()
    #
    #
    # except Exception as e:
    #     print("="*10)
    #     print(e)
    #     print("=" * 10)
    #     # raise Exception(e)
    #     return ErrorResponseDto(
    #         header=JsonHeader(jwt=dto.headers.jwt),
    #         body=ErrorResponseBody(status_code=401, message=f"Invalid jwt token")
    # )
