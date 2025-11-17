from src.domain.entities.delete_entity import DeleteEntity
from src.infra.database.repository.base_repository import BaseRepository
from src.infra.database.repository.maria_engine import get_engine
from src.infra.database.tables.table_delete import delete_cause_table


class DeleteCauseRepository(BaseRepository):
    def __init__(self):
        super(DeleteCauseRepository, self).__init__()
        self.table = delete_cause_table
        self.entity = DeleteEntity

    async def update(self, cause: str, item):
        """cause를 기준으로 업데이트하는 메서드"""
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = (
                    self.table.update()
                    .values(**item.model_dump(exclude_none=True))
                    .where(self.table.c.cause == cause)  # cause로 WHERE 조건
                )
                await conn.execute(stmt)
            return True

        except Exception as e:
            self.logger.error(f"update_by_cause error in {self.table}: {e}")
            raise e