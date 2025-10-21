from src.domain.entities import tags_entity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_tags import tags_table


class TagsRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = tags_table
        self.entity = tags_entity

    async def insert(self, item):
        await super().insert(item)

    async def select(self, item):
        await super().select(item)

    async def update(self, item_id, item):
        await super().update(item_id, item)

    async def delete(self, item):
        await super().delete(item)