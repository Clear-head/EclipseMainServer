from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.logger.custom_logger import get_logger

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

        # select(id) → select(category_id=id) 또는 적절한 컬럼명으로 변경
        # 주의: 각 repository의 테이블 구조에 맞게 컬럼명을 지정해야 합니다
        select_list.extend(await r1.select(category_id=id))
        select_list.extend(await r2.select(category_id=id))
        select_list.extend(await r3.select(category_id=id))
        select_list.extend(await r4.select(category_id=id))

        return True if select_list else False
    except Exception as ex:
        logger.error(f"before_delete_category: {id} error: {ex}")
        raise Exception(f"{id} delete category tags error") from ex