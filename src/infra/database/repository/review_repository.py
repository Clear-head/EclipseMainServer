from . import base_repository
from ..tables.table_reviews import reviews_table
from src.domain.entities.review_entity import ReviewEntity


class ReviewRepository(base_repository.BaseRepository):

    def __init__(self):
        super().__init__()
        self.table = reviews_table
        self.entity = ReviewEntity