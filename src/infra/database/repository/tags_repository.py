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

    async def select_by(self, name):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = select(self.table).where(
                    self.table.c.name == name
                )

                result = await conn.execute(stmt)
                ans = []
                for row in result.mappings():
                    ans.append(self.entity(**row))
        except Exception as e:
            self.logger.error(e)
            return []

        return ans
