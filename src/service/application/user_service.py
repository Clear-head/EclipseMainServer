from src.domain.dto.header import JsonHeader
from src.domain.dto.service.error_response import ErrorResponseDto, ErrorResponseBody
from src.domain.dto.service.user_login_dto import ToUserLoginDto, GetUserLoginDto, ToUserLoginBody
from src.infra.database.repository.users_repository import UserRepository
from src.logger.logger_handler import get_logger
from src.service.auth.jwt import create_jwt_token
from src.utils.error_handler.user_error_class import DuplicateUserInfoError, LoginFailException

class UserService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.repository = UserRepository()


    async def login(self, id: str, pw: str):
        try:
            select_from_id_pw_result = await self.repository.select_by(id=id, password=pw)

            #   id,pw 검색 인원 2명 이상
            if len(select_from_id_pw_result) > 1:
                raise DuplicateUserInfoError

            #   id or pw 틀림
            elif len(select_from_id_pw_result) == 0:
                raise LoginFailException

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
                    header=headers,
                    body=body
                )


        except LoginFailException as e:
            self.logger.error(e)
            return ErrorResponseDto(
                header=GetUserLoginDto.header,
                body=ErrorResponseBody(status_code=401, message=f"{e}")
            )

        except DuplicateUserInfoError as e:
            self.logger.error(e)
            return ErrorResponseDto(
                header=GetUserLoginDto.header,
                body=ErrorResponseBody(status_code=500, message=f"중복 유저 에러 문의 바랍니다.")
            )

        except Exception as e:
            self.logger.error(e)
            return ErrorResponseDto(
                header=GetUserLoginDto.header,
                body=ErrorResponseBody(status_code=500, message=f"{e}")
            )

    async def logout(self, id: str):
        pass

    async def register(self, id: str, pw: str):
        pass

    async def delete_account(self, id: str):
        pass

    async def find_id_pw(self, id: str, pw: str):
        pass