from starlette.responses import JSONResponse

from src.domain.dto.service.user_login_dto import ToUserLoginDto, AfterLoginUserInfo
from src.domain.dto.service.user_register_dto import ResponseRegisterDto, RequestRegisterDto
from src.infra.database.repository.users_repository import UserRepository
from src.logger.custom_logger import get_logger
from src.service.auth.jwt import create_jwt_token
from src.utils.exception_handler.auth_error_class import DuplicateUserInfoError, InvalidCredentialsException, \
    UserAlreadyExistsException


class UserService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.repository = UserRepository()


    async def login(self, id: str, pw: str):
        select_from_id_pw_result = await self.repository.select(id=id, password=pw)

        #   id,pw 검색 인원 2명 이상
        if len(select_from_id_pw_result) > 1:
            raise DuplicateUserInfoError()

        #   id or pw 틀림
        elif len(select_from_id_pw_result) == 0:
            raise InvalidCredentialsException()

        #   로그인 성공
        else:
            token1, token2 = await create_jwt_token(select_from_id_pw_result[0].id)

            info = AfterLoginUserInfo(
                    username=select_from_id_pw_result[0].username,
                    nickname=select_from_id_pw_result[0].nickname,
                    birth=select_from_id_pw_result[0].birth,
                    phone=select_from_id_pw_result[0].phone,
                    email=select_from_id_pw_result[0].email,
                    address=select_from_id_pw_result[0].address
                )
            content = ToUserLoginDto(
                message="success",
                token1=token1,
                token2=token2,
                info=info
            )

        return JSONResponse(
            content=content.model_dump()
        )

    async def logout(self, id: str):
        pass

    async def register(self, dto: RequestRegisterDto):

        select_from_id_result = await self.repository.select(id=dto.id)

        #   중복 체크
        if len(select_from_id_result) > 0:
            raise UserAlreadyExistsException()

        insert_result = await self.repository.insert(dto)

        if not insert_result:
            raise Exception("회원 가입 실패")

        else:
            msg = ResponseRegisterDto(message="success")
            return JSONResponse(
                content=msg.model_dump()
            )


    async def delete_account(self, id: str):
        pass

    async def find_id_pw(self, id: str, pw: str):
        pass