from src.domain.entities import user_like_entity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_user_like import user_like_table


class UserLikeRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = user_like_table
        self.entity = user_like_entity