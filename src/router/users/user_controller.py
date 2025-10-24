from fastapi import APIRouter
from src.domain.dto.service.user_login_dto import GetUserLoginDto
from src.domain.dto.service.user_register_dto import RequestRegisterBody
from src.logger.logger_handler import get_logger
from src.service.application.user_service import UserService


router = APIRouter(prefix="/api/users", tags=["users"])
logger = get_logger(__name__)
user_service = UserService()


#   로그인
@router.post('/session')
async def user_login(user_info: GetUserLoginDto):

    try:

        id = user_info.body.id
        password = user_info.body.password

        return await user_service.login(id, password)

    except Exception as e:
        logger.error(f"login failed: {e}")
        raise Exception(e)


#   로그아웃
@router.put('/session')
async def user_logout(get_by_user):
    if get_by_user.body.type == "login":
        pass


#   회원가입
@router.post('/register')
async def register(dto: RequestRegisterBody):
    pass


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