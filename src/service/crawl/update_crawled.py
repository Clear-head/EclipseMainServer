import asyncio

from src.domain.dto.insert_category_dto import InsertCategoryDto
from src.domain.entities.category_entity import CategoryEntity
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.tags_repository import TagsRepository
from src.logger.logger_handler import get_logger

logger = get_logger(__name__)
async def update_category(dto: InsertCategoryDto) -> int:
    logger.info(f"Updating category: {dto.name}")

    repository = CategoryRepository()
    result = await repository.select_by(name=dto.name, type=dto.type)

    #   항목 중복 업데이트 불가
    if len(result) > 1:
        logger.error(f"Found {len(result)} results for category {dto.name}")
        return -1
    elif len(result) == 0:
        logger.error(f"No results for category {dto.name} plz insert category")
        return 0
    else:
        id = result[0].id
        entity = CategoryEntity.from_dto(result[0], id)
        await repository.update(id, entity)

        logger.info(f"successful Updated category: {dto.name}")
        return 1


async def update_tags(name: str):
    logger.info(f"Updating tags")

    repository = TagsRepository()

    a = await repository.select_by(name=name)

    if len(a) > 1:
        logger.error(f"Found {len(a)} results for tag {name}")
        return -1
    elif len(a) == 0:
        logger.error(f"No results for tag {name} plz insert tag")
        return 0
    else:
        id = a[0].id
        item = {"name": name, "id": id}
        await repository.update(id, item)
        return 1

async def update_category_tags():
    logger.info(f"Updating category tags")