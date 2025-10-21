from . import base_repository
from ..tables.table_reviews import reviews_table
from src.domain.entities.reviews_entity import ReviewsEntity


class ReviewsRepository(base_repository.BaseRepository):

    def __init__(self):
        super().__init__()
        self.table = reviews_table
        self.entity = ReviewsEntity

    async def insert(self, item):
        await super().insert(item)

    async def select(self, item):
        await super().select(item)

    async def update(self, item_id, item):
        await super().update(item_id, item)

    async def delete(self, item):
        await super().delete(item)

    async def select_by(self, **filters):
        await super().select_by(**filters)