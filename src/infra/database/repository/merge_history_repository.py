from src.domain.entities.merge_history_entity import MergeHistoryEntity
from src.infra.database.repository.base_repository import BaseRepository
from src.infra.database.tables.table_merge_history import merge_history_table


class MergeHistoryRepository(BaseRepository):
    def __init__(self):
        super(MergeHistoryRepository, self).__init__()
        self.table = merge_history_table
        self.entity = MergeHistoryEntity