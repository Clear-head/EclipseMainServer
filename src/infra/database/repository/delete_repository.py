from src.domain.entities.delete_entity import DeleteEntity
from src.infra.database.repository.base_repository import BaseRepository
from src.infra.database.repository.maria_engine import get_engine
from src.infra.database.tables.table_delete import delete_cause_table


class DeleteCauseRepository(BaseRepository):
    def __init__(self):
        super(DeleteCauseRepository, self).__init__()
        self.table = delete_cause_table
        self.entity = DeleteEntity

    async def upsert(self, item):
        try:
            engine = await get_engine()
            entity = self.entity(**item.model_dump(exclude_none=True))

            async with engine.begin() as conn:
                data = entity.model_dump()
                stmt = self.table.upsert().values(**data)
                await conn.execute(stmt)

            return True

        except Exception as e:
            self.logger.error(f"upsert error: {e}")
            raise e