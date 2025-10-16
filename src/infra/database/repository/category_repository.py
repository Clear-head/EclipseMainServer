from src.domain.entities import category_entity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_category import category_table


class CategoryRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = category_table
        self.entity = category_entity

    async def insert(self, item):
        pass
    async def select(self, item):
        pass
    async def update(self, item_id, item):
        pass
    async def delete(self, item):
        pass