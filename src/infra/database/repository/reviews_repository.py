from . import base_repository
from ..tables.table_reviews import reviews_table
from src.domain.entities.reviews_entity import ReviewsEntity


class ReviewsRepository(base_repository.BaseRepository):

    def __init__(self):
        super().__init__()
        self.table = reviews_table
        self.entity = ReviewsEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, item, limit=None):
        return await super().select(item, limit=limit)

    async def update(self, item_id, item):
        return await super().update(item_id, item)

    async def delete(self, item):
        return await super().delete(item)

    async def select_by(self, **filters):
        return await super().select_by(**filters)

    async def select_with_join(self, user_id, join_table, dto, join_conditions: dict, **filters) -> list:
        return await super().select_with_join(user_id, join_table, dto, join_conditions, **filters)