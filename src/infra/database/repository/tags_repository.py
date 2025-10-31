from sqlalchemy import select

from src.domain.entities.tags_entity import TagsEntity
from src.infra.database.repository import base_repository
from src.infra.database.repository.maria_engine import get_engine
from src.infra.database.tables.table_tags import tags_table


class TagsRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = tags_table
        self.entity = TagsEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, **filters):
        return await super().select(**filters)

    async def update(self, item_id, item):
        return await super().update(item_id, item)

    async def delete(self, **filters):
        return await super().delete(**filters)

    async def select_last_id(self, category_type):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                tmp = 1 if category_type == 0 else 2 if category_type == 1 else 3

                stmt = select(self.table).where(self.table.c.id.startswith(tmp)).order_by(self.table.c.id.desc()).limit(1)
                result = await conn.execute(stmt)
                result = [i for i in result.mappings()]
                if result is None:
                    return 0
                entity = self.entity(**result[0])
                return entity.id

        except Exception as e:
            self.logger.error(e)
            raise Exception(f"{__name__} select error") from e
            # return 0

