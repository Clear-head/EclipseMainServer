from src.domain.entities import category_entity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_category import category_table


class CategoryRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = category_table
        self.entity = category_entity

    async def insert(self, item):
        await super().insert(item)

    async def select(self, item):
        await super().select(item)
        
    async def update(self, item_id, item):
        await super().update(item_id, item)
        
    async def delete(self, item):
        await super().delete(item)