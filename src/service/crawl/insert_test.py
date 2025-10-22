from src.domain.dto.insert_category_tags_dto import InsertCategoryTagsDTO
from src.domain.dto.insert_category_dto import InsertCategoryDto
from src.domain.entities.category_entity import CategoryEntity
from src.domain.entities.category_tags_entity import CategoryTagsEntity
from src.domain.entities.tags_entity import TagsEntity
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.infra.database.repository.tags_repository import TagsRepository
from src.logger.logger_handler import get_logger

async def insert_category(dto: InsertCategoryDto):
    logger = get_logger(__name__)
    logger.info(f"Inserting category: {dto.name}")

    try:
        repository = CategoryRepository()
        entity = CategoryEntity.from_dto(dto)
        await repository.insert(entity)  # ✅ await 추가
        
        logger.info(f"Inserting category successes: {dto.name}")
        return entity.id

    except Exception as e:
        logger.error(f"error insert category: {e}")
        raise Exception(e)


async def insert_category_tags(dto: InsertCategoryTagsDTO):
    logger = get_logger(__name__)
    logger.info(f"Inserting category tags: category_id={dto.category_id}, tag_id={dto.tag_id}")  # ✅ name 대신 ids 사용

    try:
        repository = CategoryTagsRepository()
        entity = CategoryTagsEntity.from_dto(dto)
        await repository.insert(entity)

        logger.info(f"Inserting category tags successes: category_id={dto.category_id}, tag_id={dto.tag_id}")
        return True

    except Exception as e:
        logger.error(f"error insert category tags {e}")
        raise Exception(e)


async def insert_tags(name: str, category_type: int):
    logger = get_logger(__name__)
    logger.info(f"Inserting tags: {name}")

    try:
        repository = TagsRepository()
        result = await repository.select_by(name=name)
        print(result)

        if len(result) == 0:
            last_id = await repository.select_last_id(category_type) + 1
<<<<<<< HEAD
            entity = TagsEntity(id=last_id, name=name)
            await repository.insert(entity)
            logger.info(f"Inserting tags successes: {name} (new id={last_id})")
            return last_id
        else:
            logger.info(f"Tag already exists: {name} (id={result[0].id})")
            return result[0].id
=======
            await repository.insert(TagsEntity(id=last_id, name=name))
        else:
            last_id = result[0].id

>>>>>>> f2b1c6a81f43a9307aef505afdf98b61bae2eca0

    except Exception as e:
        logger.error(f"error insert tags: {e}")
        raise Exception(e)