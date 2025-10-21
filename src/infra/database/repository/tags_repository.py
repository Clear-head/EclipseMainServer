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
        await super().insert(item)

    async def select(self, item):
        await super().select(item)

    async def update(self, item_id, item):
        await super().update(item_id, item)

    async def delete(self, item):
        await super().delete(item)

    async def select_by(self, **filters):
        await super().select_by(**filters)

    async def select_last_id(self, category_type):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                tmp = 1 if category_type == 0 else 2 if category_type == 2 else 3

                stmt = select(self.table).where(self.table.c.id.startswith(tmp)).order_by(self.table.c.id.desc()).limit(1)
                result = await conn.execute(stmt)
                entity = self.entity(**result.scalar())

        except Exception as e:
            self.logger.error(e)
            # raise Exception(f"{__name__} select error")
            return 0

        return entity.id if entity else 0