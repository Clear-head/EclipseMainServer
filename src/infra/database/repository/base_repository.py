from sqlalchemy import insert, select, update, delete
from sqlalchemy.exc import IntegrityError

from src.infra.database.repository.maria_engine import get_engine
from src.logger.custom_logger import get_logger


class BaseRepository:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.table = None
        self.entity = None

    async def insert(self, item):
        try:
            engine = await get_engine()
            entity = self.entity(
                **item.model_dump(exclude_none=True),
            )


            async with engine.begin() as conn:
                data = entity.model_dump()
                stmt = self.table.insert().values(**data)
                await conn.execute(stmt)

        except IntegrityError as e:
            self.logger.error(f" uuid duplicate error: {e}")
            raise e

        except Exception as e:
            self.logger.error(f" insert error: {e}")
            raise e

        return True

    async def select(self, item_id, limit=None):
        ans = []
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = self.table.select().where(self.table.c.id == item_id)

                if limit is not None:
                    stmt = stmt.limit(limit)

                result = await conn.execute(stmt)

                result = [i for i in result.mappings()]

                if not result:
                    self.logger.info(f"no item in {self.table} id: {item_id}")

                else:
                    for row in result:
                        tmp = self.entity(**row)
                        ans.append(tmp)

                return ans


        except Exception as e:
            self.logger.error(f" select from {self.table} : error: {e}")
            raise e



    async def select_by(self, limit=None, **filters) -> list:
        """

            조건 조회

            select_by(user_id=5, status='active')
            -> SELECT * FROM table WHERE user_id = 5 AND phone = '01012341234'

        """
        ans = []
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = self.table.select()

                for column, value in filters.items():
                    if hasattr(self.table.c, column):
                        stmt = stmt.where(getattr(self.table.c, column) == value)

                if limit is not None:
                    stmt = stmt.limit(limit)

                result = await conn.execute(stmt)
                result = [i for i in result.mappings()]
                if len(result) == 0 or result is None:
                    self.logger.info(f"no item in {self.table}")
                else:
                    for row in result:
                        tmp = self.entity(**row)
                        ans.append(tmp)

            return ans

        except Exception as e:
            self.logger.error(f"select_by {self.table} error {e}")
            raise e

    async def update(self, item_id, item):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = self.table.update().values(**item.model_dump()).where(self.table.c.id == item_id)
                await conn.execute(stmt)
        except Exception as e:
            self.logger.error(f"update {self.table} error: {e}")
            raise e

        return True

    async def delete(self, item_id):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = self.table.delete().where(self.table.c.id == item_id)
                result = await conn.execute(stmt)


        except Exception as e:
            self.logger.error(f"delete {self.table} error: {e}")
            raise e

        return True

