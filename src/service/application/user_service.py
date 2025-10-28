from src.domain.dto.header import JsonHeader
from src.domain.dto.service.user_login_dto import ToUserLoginDto, ToUserLoginBody
from src.domain.dto.service.user_register_dto import RequestRegisterBody, ResponseRegisterDto, ResponseRegisterBody
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
        select_from_id_pw_result = await self.repository.select_by(id=id, password=pw)

        #   id,pw 검색 인원 2명 이상
        if len(select_from_id_pw_result) > 1:
            raise DuplicateUserInfoError()

        #   id or pw 틀림
        elif len(select_from_id_pw_result) == 0:
            raise InvalidCredentialsException()

        #   로그인 성공
        else:
            token1, token2 = await create_jwt_token(select_from_id_pw_result[0].id)

            headers = JsonHeader(
                content_type="application/json",
                jwt=None                #   바디에 토큰 담아서 전달
            )

            body = ToUserLoginBody(
                status_code=200,
                message="success",
                token1=token1,
                token2=token2
            )

            return ToUserLoginDto(
                headers=headers,
                body=body
            )

    async def logout(self, id: str):
        pass

    async def register(self, dto: RequestRegisterBody):

        select_from_id_result = await self.repository.select_by(id=id)

        if len(select_from_id_result) > 0:
            raise UserAlreadyExistsException()

        insert_result = await self.repository.insert(dto)

        if not insert_result:
            raise Exception("회원 가입 실패")

        else:
            return ResponseRegisterDto(
                headers=JsonHeader(
                    content_type="application/json",
                    jwt=None
                ),
                body=ResponseRegisterBody(
                    status_code=200,
                    message="success",
                )
            )



    async def delete_account(self, id: str):
        pass

    async def find_id_pw(self, id: str, pw: str):
        pass