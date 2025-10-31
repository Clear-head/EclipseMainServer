from src.domain.entities.reviews_entity import ReviewsEntity
from . import base_repository
from ..tables.table_reviews import reviews_table


class ReviewsRepository(base_repository.BaseRepository):

    def __init__(self):
        super().__init__()
        self.table = reviews_table
        self.entity = ReviewsEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, **filters):
        return await super().select(**filters)

    async def update(self, item_id, item):
        return await super().update(item_id, item)

    async def delete(self, **filters):
        return await super().delete(**filters)
