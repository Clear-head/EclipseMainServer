from fastapi import APIRouter

from src.domain.dto.header import JsonHeader
from src.domain.dto.service.request_jwt_dto import RequestAccessTokenDto, RequestAccessTokenBody, \
    ResponseAccessTokenBody
from src.domain.dto.service.user_login_dto import GetUserLoginDto, ToUserLoginBody, ToUserLoginDto
from src.domain.dto.service.user_register_dto import RequestRegisterBody, RequestRegisterDto
from src.logger.custom_logger import get_logger
from src.service.application.user_service import UserService
from src.service.auth.jwt import validate_jwt_token, create_jwt_token
from src.utils.exception_handler.auth_error_class import MissingTokenException, ExpiredRefreshTokenException

router = APIRouter(prefix="/api/users", tags=["users"])
logger = get_logger(__name__)
user_service = UserService()


#   로그인
@router.post('/session')
async def user_login(user_info: GetUserLoginDto):
    id = user_info.body.id
    password = user_info.body.password

    return await user_service.login(id, password)


#   로그아웃
@router.put('/session')
async def user_logout(get_by_user):
    if get_by_user.body.type == "login":
        pass


#   회원가입
@router.post('/register')
async def register(dto: RequestRegisterDto):
    try:
        return await user_service.register(dto.body)
    except Exception as e:
        logger.error(f"register failed: {e}")
        raise e


#   회원탈퇴
@router.delete('/register')
async def delete_account():
    pass


#   아이디 찾기
@router.post('/id')
async def find_user_id():
    pass


#   비밀번호
@router.post('/password')
async def find_user_pw():
    pass


#   refresh jwt
@router.get("/refresh")
@router.post("/refresh")
async def to_refresh(dto: RequestAccessTokenDto):
    jwt = dto.body.token

    if jwt is None:
        logger.error("Missing token")
        raise MissingTokenException()

    validate_result = await validate_jwt_token(jwt)
    if validate_result == 2:
        #   todo: 세션에서 삭제
        #       로그아웃 까지
        raise ExpiredRefreshTokenException()

    token1, token2 = await create_jwt_token("refresh")

    headers = JsonHeader(
        content_type="application/json",
        jwt=None  # 바디에 토큰 담아서 전달
    )

    body = RequestAccessTokenBody(
        token=token1
    )

    return ResponseAccessTokenBody(
        headers=headers,
        body=body
    )