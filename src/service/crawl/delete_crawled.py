import asyncio

from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.logger.logger_handler import get_logger

logger = get_logger(__name__)

async def delete_category(id: str):
    """
        Warning! 이 메서드 실행 전 해당 카테고리에 연결 되어있는 친구들 부터 삭제(ex. category tags, reviews, user history, user like)
    """
    try:
        logger.info(f"delete_category: {id}")

        if await before_delete_category(id):
            logger.error(f"다른 테이블 삭제 먼저 하기: {id}")
            raise Exception(f"다른 테이블 삭제 먼저 하기")

        repository = CategoryRepository()
        flag = await repository.delete(id)

        if flag:
            logger.info(f"successful delete_category: {id}")
        else:
            raise Exception(f"{id} delete category error")
    except Exception as ex:
        logger.error(f"delete category error: {ex}")
        raise Exception(f"{id} delete category error")

async def delete_category_tags(id: str):
    logger.info(f"delete_category_tags: {id}")
    repository = CategoryTagsRepository()

    flag = await repository.delete(id)
    if flag:
        logger.info(f"successful delete_category_tags: {id}")
    else:
        raise Exception(f"{id} delete category tags error")


async def before_delete_category(id: str):
    from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
    from src.infra.database.repository.reviews_repository import ReviewsRepository
    from src.infra.database.repository.user_like_repository import UserLikeRepository
    from src.infra.database.repository.user_history_repository import UserHistoryRepository
    try:
        logger.info(f"before_delete_category: {id}")
        r1 = CategoryTagsRepository()
        r2 = ReviewsRepository()
        r3 = UserHistoryRepository()
        r4 = UserLikeRepository()

        select_list = []

        select_list.extend(await r1.select(id))
        select_list.extend(await r2.select(id))
        select_list.extend(await r3.select_by(category_id=id))
        select_list.extend(await r4.select_by(category_id=id))

        return True if select_list else False
    except Exception as ex:
        logger.error(f"before_delete_category: {id} error: {ex}")
        raise Exception(f"{id} delete category tags error") from ex



asyncio.run(delete_category("7e409879-aa59-46a7-bb42-6de8e98ecb93"))