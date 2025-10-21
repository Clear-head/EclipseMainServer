from src.domain.entities import category_tags_entity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_category_tags import category_tags_table


class CategoryTagsRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = category_tags_table
        self.entity = category_tags_entity

    async def insert(self, item):
        await super().insert(item)

    async def select(self, item):
        await super().select(item)

    async def update(self, item_id, item):
        await super().update(item_id, item)

    async def delete(self, item):
        await super().delete(item)