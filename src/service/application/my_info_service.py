from src.domain.dto.service.user_like_dto import ResponseUserHistoryDTO, UserLikeDTO, ResponseUserLikeDTO, \
    UserReviewDTO, ResponseUserReviewDTO, UserHistoryDTO
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.user_history_repository import UserHistoryRepository
from src.infra.database.repository.user_like_repository import UserLikeRepository
from src.infra.database.repository.users_repository import UserRepository
from src.infra.database.tables.table_category import category_table
from src.logger.custom_logger import get_logger
from src.utils.exception_handler.service_error_class import NotFoundAnyItemException


class UserInfoService:
    def __init__(self):
        self.logger = get_logger(__name__)

    async def get_user_like(self, user_id) -> ResponseUserLikeDTO:
        repo = UserLikeRepository()

        liked = await repo.select(
            return_dto=UserLikeDTO,
            id=user_id,
            join=[
                {
                    "table": category_table,
                    "on": {"category_id": "id"},
                    "alias": "category"
                }
            ],
            columns={
                "category_id": "category_id",
                "category.name": "category_name",
                "category.image": "category_image",
                "category.sub_category": "sub_category",
                "category.do": "do",
                "category.si": "si",
                "category.gu": "si",
                "category.detail_address": "detail_address"
            }
        )
        print(liked[0])


        if not liked:
            self.logger.info(f"no like for {user_id}")
            raise NotFoundAnyItemException()

        else:
            return ResponseUserLikeDTO(
                like_list=liked
            )


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