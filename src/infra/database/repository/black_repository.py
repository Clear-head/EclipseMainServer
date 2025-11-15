from src.domain.entities.black_entity import BlackEntity
from src.infra.database.repository.base_repository import BaseRepository
from src.infra.database.tables.table_black import black_table


class BlackRepository(BaseRepository):
    def __init__(self):
        super(BlackRepository, self).__init__()
        self.table = black_table
        self.entity = BlackEntity
