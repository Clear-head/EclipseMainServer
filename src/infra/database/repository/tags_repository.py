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