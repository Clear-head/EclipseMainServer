import traceback

from fastapi import APIRouter

from src.domain.dto.header import JsonHeader
from src.domain.dto.service.error_response import ErrorResponseDto, ErrorResponseBody
from src.domain.dto.service.main_screen_dto import RequestMainScreenDTO
from src.logger.custom_logger import get_logger
from src.service.application.main_service import MainService
from src.service.auth.jwt import validate_jwt_token

router = APIRouter(prefix="/api/service")
logger = get_logger(__name__)



@router.post("/main")
@router.get("/main")
async def to_main_screen(dto: RequestMainScreenDTO):
    try:
        jwt = dto.headers.jwt
        print(jwt)

        if jwt is None:
            logger.error("Invalid token")
            raise Exception('Invalid token')

        elif await validate_jwt_token(jwt) != 1:
            raise Exception('JWT validation error')

        else:
            main_service_class = MainService()
            return await main_service_class.to_main()


    except Exception as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()
        logger.error(type(e).__name__ + str(e))

        return ErrorResponseDto(
            header=JsonHeader(jwt=dto.headers.jwt),
            body=ErrorResponseBody(status_code=401, message=f"Invalid jwt token")
        )
