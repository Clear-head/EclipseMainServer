from src.domain.dto.service.change_nickname_dto import RequestChangeNicknameDto, ResponseChangeNicknameDto
from src.domain.dto.service.user_like_dto import UserLikeDTO, ResponseUserLikeDTO, RequestSetUserLikeDTO
from src.domain.dto.service.user_reivew_dto import RequestGetUserReviewDTO
from src.domain.entities.user_entity import UserEntity
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.user_like_repository import UserLikeRepository
from src.infra.database.repository.users_repository import UserRepository
from src.infra.database.tables.table_category import category_table
from src.logger.custom_logger import get_logger
from src.utils.exception_handler.auth_error_class import UserNotFoundException, DuplicateUserInfoError


class UserInfoService:
    def __init__(self):
        self.logger = get_logger(__name__)


    async def set_my_like(self, data: RequestSetUserLikeDTO, type: bool) -> str:
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
                "category.detail_address": "detail_address"
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

    async def change_nickname(self, dto: RequestChangeNicknameDto):
        self.logger.info(f"try nickname change id: {dto.user_id}")
        repo = UserRepository()

        result = await repo.select(id=dto.user_id)

        if not result:
            raise UserNotFoundException()

        elif len(result) > 1:
            raise DuplicateUserInfoError()

        else:
            result = result[0]
            user_entity = UserEntity(
                id=dto.user_id,
                username=result.username,
                nickname=dto.nickname,
                password=result.password,
                email=result.email,
            )

            await repo.update(dto.user_id, user_entity)

        return ResponseChangeNicknameDto(
            msg=dto.nickname
        )

    async def set_user_reivew(self, dto: RequestGetUserReviewDTO):
        repo = ReviewsRepository()

        result = await repo.select(id=dto.user_id, category_id=dto.category_id)



    # async def get_user_review(self, user_id) -> ResponseUserReviewDTO:
    #     repo = ReviewsRepository()
    #     reviews = await repo.select_with_join(
    #         user_id=user_id,
    #         join_table=category_table,
    #         dto=UserReviewDTO,
    #         join_conditions={
    #             "category_id": "id"
    #         },
    #         select_columns={
    #             'main': ["category_id"],
    #             'join': {
    #                 'name': 'category_name',
    #                 "image": 'category_image',
    #                 "sub_category": "sub_category",
    #                 "do": "do",
    #                 "si": "si",
    #                 "gu": "gu",
    #                 "detail_address": "detail_address"
    #             }
    #         }
    #
    #     )
    #     if not reviews:
    #         self.logger.info(f"no review for {user_id}")
    #         raise NotFoundAnyItemException()
    #
    #     else:
    #         for review in reviews:
    #             tmp.append(
    #                 UserReviewDTO(
    #                     review
    #                 )
    #             )
    #
    #
    # async def get_user_history(self, user_id):
    #     repo = UserHistoryRepository()
    #
    #     history = await repo.select_with_join(
    #         user_id=user_id,
    #         join_table=category_table,
    #         dto=UserHistoryDTO,
    #         join_conditions={
    #             "category_id": "id"
    #         },
    #         select_columns={
    #             'main': ["category_id"],
    #             'join': {
    #                 'name': 'category_name',
    #                 "image": 'category_image',
    #                 "sub_category": "sub_category",
    #                 "do": "do",
    #                 "si": "si",
    #                 "gu": "gu",
    #                 "detail_address": "detail_address"
    #             }
    #         }
    #
    #     )
    #
    #
    #     if not history:
    #         self.logger.info(f"no history for {user_id}")
    #         raise NotFoundAnyItemException()
    #
    #     return history