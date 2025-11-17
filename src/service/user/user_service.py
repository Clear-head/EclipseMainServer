from src.domain.dto.user.user_account_dto import RequestDeleteAccountDTO
from src.domain.dto.user.user_auth_dto import UserInfoDTO, ResponseLoginDTO, RequestRegisterDTO, ResponseRegisterDTO
from src.domain.dto.user.user_profile_dto import RequestUpdateProfileDTO, ResponseUpdateProfileDTO
from src.domain.entities.delete_entity import DeleteEntity
from src.domain.entities.user_entity import UserEntity
from src.infra.database.repository.black_repository import BlackRepository
from src.infra.database.repository.delete_repository import DeleteCauseRepository
from src.infra.database.repository.users_repository import UserRepository
from src.logger.custom_logger import get_logger
from src.service.auth.jwt import create_jwt_token
from src.utils.exception_handler.auth_error_class import DuplicateUserInfoError, InvalidCredentialsException, \
    UserAlreadyExistsException, UserNotFoundException, UserBannedException


class UserService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.repository = UserRepository()

    #   내정보 수정
    async def change_info(self, dto: RequestUpdateProfileDTO, field: str, user_id):
        self.logger.info(f"try {field} change id: {user_id}")

        result = await self.repository.select(id=user_id, password=dto.password)

        if not result:
            raise UserNotFoundException()

        elif len(result) > 1:
            raise DuplicateUserInfoError()

        else:
            user_entity = None
            result = result[0]

            if field == "nickname":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=dto.change_field,
                    password=result.password,
                    email=result.email,
                )

            elif field == "password":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=result.nickname,
                    password=dto.change_field,
                    email=result.email,
                )

            elif field == "email":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=result.nickname,
                    email=dto.change_field,
                    password=result.password
                )

            elif field == "address":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=result.nickname,
                    email=result.email,
                    address=dto.change_field,
                    password=result.password,
                )

            elif field == "phone":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=result.nickname,
                    email=result.email,
                    password=result.password,
                    phone=dto.change_field,
                )

            await self.repository.update(user_id, user_entity)

        return ResponseUpdateProfileDTO(
            msg=dto.change_field
        )


    async def login(self, id: str, pw: str):
        select_from_id_pw_result = await self.repository.select(id=id, password=pw)

        #   id,pw 검색 인원 2명 이상
        if len(select_from_id_pw_result) > 1:
            raise DuplicateUserInfoError()

        #   id or pw 틀림
        elif len(select_from_id_pw_result) == 0:
            raise InvalidCredentialsException()

        banned = await BlackRepository().select(user_id=select_from_id_pw_result[0].id)
        if len(banned) > 0:
            raise UserBannedException(finished_at=banned[0].finished_at)

        #   로그인 성공
        else:
            token1, token2 = await create_jwt_token(select_from_id_pw_result[0].id)

            info = UserInfoDTO(
                    username=select_from_id_pw_result[0].username,
                    nickname=select_from_id_pw_result[0].nickname,
                    birth=select_from_id_pw_result[0].birth,
                    phone=select_from_id_pw_result[0].phone,
                    email=select_from_id_pw_result[0].email,
                    address=select_from_id_pw_result[0].address
                )
            content = ResponseLoginDTO(
                message="success",
                token1=token1,
                token2=token2,
                info=info
            )

        return content

    async def logout(self, id: str):
        pass

    async def register(self, dto: RequestRegisterDTO):

        select_from_id_result = await self.repository.select(id=dto.id)

        #   중복 체크
        if len(select_from_id_result) > 0:
            raise UserAlreadyExistsException()

        insert_result = await self.repository.insert(dto)

        if not insert_result:
            raise Exception("회원 가입 실패")

        else:
            return ResponseRegisterDTO(message="success")


    async def delete_account(self, id: str, dto: RequestDeleteAccountDTO):
        result = await self.repository.select(id=id, password=dto.password)


        if not result:
            raise UserNotFoundException()
        elif len(result) > 1:
            raise DuplicateUserInfoError()
        else:

            repo = DeleteCauseRepository()
            tmp = await repo.select(cause = dto.because)
            if tmp:
                await repo.update(
                    dto.because,
                    item = DeleteEntity(
                        count=tmp[0].count+1,
                        cause=dto.because
                    )
                )
            else:
                await repo.insert(
                    DeleteEntity(
                        count=1,
                        cause=dto.because
                    )
                )
            return await self.repository.delete(id=id, password=dto.password)

    async def find_id_pw(self, id: str, pw: str):
        pass