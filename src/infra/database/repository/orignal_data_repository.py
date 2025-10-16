from . import base_repository
from ..tables.table_original_data import original_data_table
from src.domain.entities.original_data_entity import OriginalDataEntity

class OriginalDataRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = original_data_table
        self.entity = OriginalDataEntity


    async def bulk_insert(self, data):
        """
            대용량 처리 전용
        :param data:
        :return:
        """

    async def select_by_id(self, id: str) -> OriginalDataEntity:
        """

            아이디로 찾기

        :param id:
        :return:
        """


    async def select_by_type(self, name: str) -> list[OriginalDataEntity]:
        pass


    async def select_by_address(self, name: str) -> list[OriginalDataEntity]:
        pass