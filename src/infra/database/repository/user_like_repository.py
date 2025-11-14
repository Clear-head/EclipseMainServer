from src.domain.entities.user_like_entity import UserLikeEntity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_user_like import user_like_table


class UserLikeRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = user_like_table
        self.entity = UserLikeEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, **filters):
        return await super().select(**filters)

    async def update(self, item_id, item):
        return await super().update(item_id, item)

    async def delete(self, **filters):
        return await super().delete(**filters)
