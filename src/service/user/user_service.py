from datetime import datetime

from src.domain.dto.user.user_account_dto import RequestDeleteAccountDTO
from src.domain.dto.user.user_auth_dto import UserInfoDTO, ResponseLoginDTO, RequestRegisterDTO, ResponseRegisterDTO
from src.domain.dto.user.user_profile_dto import RequestUpdateProfileDTO, ResponseUpdateProfileDTO
from src.domain.entities.delete_entity import DeleteEntity
from src.domain.entities.user_entity import UserEntity
from src.infra.database.repository.black_repository import BlackRepository
from src.infra.database.repository.delete_repository import DeleteCauseRepository
from src.infra.database.repository.users_repository import UserRepository
from src.infra.cache.redis_repository import SessionRepository
from src.logger.custom_logger import get_logger
from src.service.auth.jwt import create_jwt_token
from src.utils.exception_handler.auth_error_class import DuplicateUserInfoError, InvalidCredentialsException, \
    UserAlreadyExistsException, UserNotFoundException, UserBannedException
from src.utils.password_utils import hash_password, verify_password


class UserService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.repository = UserRepository()

    #   내정보 수정
    async def change_info(self, dto: RequestUpdateProfileDTO, field: str, user_id):
        self.logger.info(f"try {field} change id: {user_id}")

        # 비밀번호 검증을 위해 사용자 정보 조회 (평문 비밀번호가 아닌 ID로만 조회)
        user_result = await self.repository.select(id=user_id)

        if not user_result:
            raise UserNotFoundException()
        elif len(user_result) > 1:
            raise DuplicateUserInfoError()

        user = user_result[0]

        # 입력받은 비밀번호와 저장된 해시 비밀번호 비교
        if not verify_password(dto.password, user.password):
            raise InvalidCredentialsException()

        # 비밀번호가 맞으면 필드 업데이트
        user_entity = None

        if field == "nickname":
            user_entity = UserEntity(
                id=user_id,
                username=user.username,
                nickname=dto.change_field,
                password=user.password,  # 기존 해시 비밀번호 유지
                email=user.email,
            )

        elif field == "password":
            # 새 비밀번호를 해시화
            hashed_new_password = hash_password(dto.change_field)
            user_entity = UserEntity(
                id=user_id,
                username=user.username,
                nickname=user.nickname,
                password=hashed_new_password,  # 해시화된 새 비밀번호
                email=user.email,
            )

        elif field == "email":
            user_entity = UserEntity(
                id=user_id,
                username=user.username,
                nickname=user.nickname,
                email=dto.change_field,
                password=user.password  # 기존 해시 비밀번호 유지
            )

        elif field == "address":
            user_entity = UserEntity(
                id=user_id,
                username=user.username,
                nickname=user.nickname,
                email=user.email,
                address=dto.change_field,
                password=user.password,  # 기존 해시 비밀번호 유지
            )

        elif field == "phone":
            user_entity = UserEntity(
                id=user_id,
                username=user.username,
                nickname=user.nickname,
                email=user.email,
                password=user.password,  # 기존 해시 비밀번호 유지
                phone=dto.change_field
            )

        result = await self.repository.update(user_id, user_entity)

        if result:
            return ResponseUpdateProfileDTO(msg="success")
        else:
            raise Exception(f"{field} update failed")

    async def login(self, id: str, password: str):
        # 블랙리스트 확인
        black_repo = BlackRepository()
        banned = await black_repo.select(id=id)

        if banned:
            raise UserBannedException(datetime.now())

        # ID로만 사용자 조회 (비밀번호는 해시 비교로 검증)
        user_result = await self.repository.select(id=id)

        if not user_result:
            raise InvalidCredentialsException()
        elif len(user_result) > 1:
            raise DuplicateUserInfoError()

        user = user_result[0]

        # 평문 비밀번호와 해시 비밀번호 비교
        if not verify_password(password, user.password):
            raise InvalidCredentialsException()

        token1, token2 = await create_jwt_token(user.id)
        info = UserInfoDTO(
                username=user.username,
                nickname=user.nickname,
                birth=user.birth,
                phone=user.phone,
                email=user.email,
                address=user.address
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
        # ID 중복 체크
        select_from_id_result = await self.repository.select(id=dto.id)

        if len(select_from_id_result) > 0:
            raise UserAlreadyExistsException()

        # 비밀번호 해시화
        hashed_password = hash_password(dto.password)

        # DTO의 비밀번호를 해시로 교체
        dto.password = hashed_password

        # DB에 삽입
        insert_result = await self.repository.insert(dto)

        if not insert_result:
            raise Exception("회원 가입 실패")
        else:
            return ResponseRegisterDTO(message="success")

    async def delete_account(self, id: str, dto: RequestDeleteAccountDTO, jwt: str = None):
        user_result = await self.repository.select(id=id)

        if not user_result:
            raise UserNotFoundException()
        elif len(user_result) > 1:
            raise DuplicateUserInfoError()

        user = user_result[0]

        # 비밀번호 검증
        if not verify_password(dto.password, user.password):
            raise InvalidCredentialsException()

        # 세션 삭제
        session_repo = SessionRepository()

        if jwt:
            await session_repo.delete_session(jwt)
            self.logger.info(f"JWT 세션 삭제 완료: user_id={id}")

        await session_repo.delete_chat_session(id)
        self.logger.info(f"AI 채팅 세션 삭제 완료: user_id={id}")

        # 삭제 사유 통계 업데이트
        repo = DeleteCauseRepository()
        tmp = await repo.select(cause=dto.because)

        if tmp:
            await repo.update(
                cause=dto.because,
                item=DeleteEntity(
                    count=tmp[0].count + 1,
                    cause=dto.because
                )
            )
        else:
            # 없으면 insert
            await repo.insert(
                DeleteEntity(
                    count=1,
                    cause=dto.because
                )
            )

        return await self.repository.delete(id=id)