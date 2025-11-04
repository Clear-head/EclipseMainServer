from src.domain import dto
from src.domain.dto.service.change_info_dto import ResponseChangeInfoDto, RequestChangeInfoDto
from src.domain.dto.service.user_history_dto import ResponseUserHistoryListDto, MergeUserHistory
from src.domain.dto.service.user_like_dto import UserLikeDTO, ResponseUserLikeDTO, RequestSetUserLikeDTO
from src.domain.dto.service.user_reivew_dto import ResponseUserReviewDTO, RequestGetUserReviewDTO, \
    UserReviewDTO
from src.domain.entities.merge_history_entity import MergeHistoryEntity
from src.domain.entities.user_entity import UserEntity
from src.domain.entities.user_history_entity import UserHistoryEntity
from src.infra.database.repository.merge_history_repository import MergeHistoryRepository
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.user_history_repository import UserHistoryRepository
from src.infra.database.repository.user_like_repository import UserLikeRepository
from src.infra.database.repository.users_repository import UserRepository
from src.infra.database.tables.table_category import category_table
from src.logger.custom_logger import get_logger
from src.utils.exception_handler.auth_error_class import UserNotFoundException, DuplicateUserInfoError


class UserInfoService:
    def __init__(self):
        self.logger = get_logger(__name__)

    async def change_info(self, dto: RequestChangeInfoDto, field: str):
        self.logger.info(f"try {field} change id: {dto.user_id}")
        repo = UserRepository()

        result = await repo.select(id=dto.user_id, password=dto.password)

        if not result:
            raise UserNotFoundException()

        elif len(result) > 1:
            raise DuplicateUserInfoError()

        else:
            result = result[0]

            if field == "nickname":
                user_entity = UserEntity(
                    id=dto.user_id,
                    username=result.username,
                    nickname=dto.change_field,
                    password=result.password,
                    email=result.email,
                )

            elif field == "password":
                user_entity = UserEntity(
                    id=dto.user_id,
                    username=result.username,
                    nickname=result.nickname,
                    password=dto.change_field,
                    email=result.email,
                )

            elif field == "email":
                user_entity = UserEntity(
                    id=dto.user_id,
                    username=result.username,
                    nickname=result.nickname,
                    email=dto.change_field,
                    password=result.password
                )

            elif field == "address":
                user_entity = UserEntity(
                    id=dto.user_id,
                    username=result.username,
                    nickname=result.nickname,
                    email=result.email,
                    address=dto.change_field,
                    password=result.password,
                )

            elif field == "phone":
                user_entity = UserEntity(
                    id=dto.user_id,
                    username=result.username,
                    nickname=result.nickname,
                    email=result.email,
                    password=result.password,
                    phone=dto.change_field,
                )

            await repo.update(dto.user_id, user_entity)

        return ResponseChangeInfoDto(
            msg=dto.change_field
        )


    async def set_my_like(self, data: RequestSetUserLikeDTO, type: bool) -> str:
        self.logger.info(f"try {data.user_id} set my like: {type}")
        repo = UserLikeRepository()

        if not type:
            flag = await repo.delete(user_id=data.user_id, category_id=data.category_id)
        else:
            flag = await repo.insert(data)

        if not flag:
            self.logger.error(f"찜 목록 설정 실패 user: {data.user_id}, category: {data.category_id}")
            raise Exception(f"찜 목록 설정 실패 user: {data.user_id}, category: {data.category_id}")

        else:
            return "success"



    async def get_user_like(self, user_id) -> ResponseUserLikeDTO:
        self.logger.info(f"try {user_id} get user like: {user_id}")
        repo = UserLikeRepository()

        liked = await repo.select(
            return_dto=UserLikeDTO,
            user_id=user_id,
            joins=[
                {
                    "table": category_table,
                    "on": {"category_id": "id"},
                    "alias": "category"
                }
            ],
            columns={
                "category.type": "type",
                "category.id": "category_id",
                "category.name": "category_name",
                "category.image": "category_image",
                "category.sub_category": "sub_category",
                "category.do": "do",
                "category.si": "si",
                "category.gu": "gu",
                "category.detail_address": "detail_address",
                # "stars": "stars",
                # "created_at": "created_at",
            }
        )


        if not liked:
            self.logger.info(f"no like for {user_id}")
            # raise NotFoundAnyItemException()
            return ResponseUserLikeDTO(
                like_list=[]
            )

        else:
            return ResponseUserLikeDTO(
                like_list=liked
            )


    async def set_user_reivew(self, dto: RequestGetUserReviewDTO):
        repo = ReviewsRepository()

        result = await repo.select(id=dto.user_id, category_id=dto.category_id)



    async def get_user_reviews(self, user_id) -> ResponseUserReviewDTO:
        self.logger.info(f"try {user_id} get user review: {user_id}")
        review_repo = ReviewsRepository()

        result = await review_repo.select(
            return_dto=UserReviewDTO,
            joins=[
                {
                    "table": category_table,
                    "on": {"category_id": "id"},
                    "alias": "category"
                }
            ],
            columns={
                "id": "review_id",
                "comment": "comment",
                "stars": "stars",
                "category.name": "category_name",
                "created_at": "created_at"
            },
            user_id=user_id,
        )

        return ResponseUserReviewDTO(
            review_list=result
        )

    async def get_user_history_list(self, user_id):
        self.logger.info(f"try {user_id} get user history list: {user_id}")
        repo = MergeHistoryRepository()

        result = await repo.select(
            user_id=user_id,
            desc=MergeHistoryEntity.visited_at
        )

        results = [
            MergeUserHistory(
                id=item.id,
                visited_at=item.visited_at,
                categories_name=item.categories_name
            )
            for item in result
        ]

        return ResponseUserHistoryListDto(
            results=results
        )


    async def get_user_history(self, user_id, merge_history_id):
        self.logger.info(f"try {user_id} get user history: {user_id}")
        repo = UserHistoryRepository()

        result = await repo.select(
            user_id=user_id,
            merge_history_id=merge_history_id,
            order_by=UserHistoryEntity.order
        )

