from src.domain.entities.category_tags_entity import CategoryTagsEntity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_category_tags import category_tags_table


class CategoryTagsRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = category_tags_table
        self.entity = CategoryTagsEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, **filters):
        return await super().select(**filters)

    async def update(self, item_id, item):
        return await super().update(item_id, item)

    async def delete(self, **filters):
        return await super().delete(**filters)
