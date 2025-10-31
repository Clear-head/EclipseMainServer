from src.domain.entities.user_entity import UserEntity
from . import base_repository
from ..tables.table_users import users_table


class UserRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = users_table
        self.entity = UserEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, **filters):
        return await super().select(**filters)

    async def update(self, item_id, item):
        return await super().update(item_id, item)

    async def delete(self, **filters):
        return await super().delete(**filters)
