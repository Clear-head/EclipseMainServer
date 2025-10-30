from src.domain.entities.user_history_entity import UserHistoryEntity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_user_history import user_history_table



class UserHistoryRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = user_history_table
        self.entity = UserHistoryEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, **filters):
        return await super().select(**filters)

    async def update(self, item_id, item):
        return await super().update(item_id, item)

    async def delete(self, **filters):
        return await super().delete(**filters)
