from src.domain.dto.crawled.insert_category_dto import InsertCategoryDto
from src.domain.dto.crawled.insert_category_tags_dto import InsertCategoryTagsDTO
from src.domain.entities.category_entity import CategoryEntity
from src.domain.entities.category_tags_entity import CategoryTagsEntity
from src.domain.entities.tags_entity import TagsEntity
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.infra.database.repository.tags_repository import TagsRepository
from src.logger.custom_logger import get_logger

async def insert_category(dto: InsertCategoryDto):
    logger = get_logger(__name__)
    logger.info(f"Inserting category: {dto.name}")

    try:
        flag = False
        repository = CategoryRepository()
        entity = CategoryEntity

        while not flag:
            entity = CategoryEntity.from_dto(dto)

            # select_by() → select()로 변경
            if len(
                    await repository.select(
                        name=entity.name,
                        si=entity.si,
                        gu=entity.gu,
                        detail_address=entity.detail_address
                    )
            ) > 0:
                raise Exception(f"duplicate category: {dto.name}")

            flag = await repository.insert(entity)
    except Exception as e:
        logger.error(e)
        raise Exception(e)

    logger.info(f"Inserting category successes: {dto.name}")
    return entity.id


async def insert_category_tags(dto: InsertCategoryTagsDTO):
    logger = get_logger(__name__)
    logger.info(f"Inserting category tags: {dto}")

    try:
        repository = CategoryTagsRepository()
        entity = CategoryTagsEntity.from_dto(dto)
        await repository.insert(entity)

    except Exception as e:
        logger.error(f"error insert category tags {e}")
        raise Exception(e)

    logger.info(f"Inserting category tags successes: {dto}")
    return True


async def insert_tags(name: str, category_type: int):
    logger = get_logger(__name__)
    logger.info(f"Inserting tags: {name}")

    try:
        repository = TagsRepository()
        # select_by() → select()로 변경
        result = await repository.select(name=name)
        print(result)

        if len(result) == 0:
            last_id = await repository.select_last_id(category_type) + 1
            await repository.insert(TagsEntity(id=last_id, name=name))
        else:
            last_id = result[0].id

    except Exception as e:
        logger.error(f"error insert tags: {e}")
        raise Exception(e)

    logger.info(f"Inserting tags successes: {name}")
    return last_id