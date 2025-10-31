from src.domain.dto.crawled.insert_category_dto import InsertCategoryDto
from src.domain.dto.crawled.insert_category_tags_dto import InsertCategoryTagsDTO
from src.domain.entities.category_entity import CategoryEntity
from src.domain.entities.category_tags_entity import CategoryTagsEntity
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.logger.custom_logger import get_logger

async def update_category(dto: InsertCategoryDto) -> str:
    try:
        logger = get_logger(__name__)
        logger.info(f"Updating category: {dto.name}")

        repository = CategoryRepository()
        # select_by() → select()로 변경
        result = await repository.select(name=dto.name, type=dto.type, detail_address=dto.detail_address)

        #   항목 중복 or 없어서 업데이트 불가
        if len(result) != 1:
            raise Exception(f"Found {len(result)} results for category {dto.name}")

        else:
            id = result[0].id
            entity = CategoryEntity.from_dto(dto, id=id)
            flag = await repository.update(id, entity)

            if flag:
                logger.info(f"successful Updated category: {dto}")
                return id
            else:
                logger.info(f"failed Updated category: {dto}")
                raise Exception(f"failed Updated category: {dto.id}")

    except Exception as e:
        logger.error(e)
        raise Exception(f"update category error: {dto.name, e}")

async def update_category_tags(dto: InsertCategoryTagsDTO) -> int:
    try:
        logger = get_logger(__name__)
        logger.info(f"Updating category tags")
        repository = CategoryTagsRepository()
        # select_by() → select()로 변경
        result = await repository.select(tag_id=dto.tag_id, category_id=dto.category_id)

        #   중복이거나 항목 없으면 error
        if len(result) != 1:
            raise Exception(f"Found {len(result)} results ")

        else:
            id = result[0].id
            entity = CategoryTagsEntity.from_dto(dto, id=id)
            print(entity)
            flag = await repository.update(id, entity)

            if flag:
                logger.info(f"successful Updated category tags")
                return id

            else:
                logger.info(f"failed Updated category tags:")
                raise Exception(f"failed Updated category tags")

    except Exception as e:
        logger.error(e)
        raise Exception(f"update category tags error: {e}")