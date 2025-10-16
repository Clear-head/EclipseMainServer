from src.domain.entities import user_history_entity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_user_history import user_history_table



class UserHistoryRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = user_history_table
        self.entity = user_history_entity

    async def insert(self, item):
        pass
    async def select(self, item):
        pass
    async def update(self, item_id, item):
        pass
    async def delete(self, item):
        pass