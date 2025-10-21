from sqlalchemy import insert, select, update, delete
from sqlalchemy.exc import IntegrityError

from src.infra.database.repository.maria_engine import get_engine
from src.logger.logger_handler import get_logger


class BaseRepository:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.table = None
        self.entity = None

    async def insert(self, item):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:

                stmt = insert(self.table).values(**item)
                await conn.execute(stmt)

        except IntegrityError as e:
            self.logger.error(f"{__name__} uuid duplicate error: {e}")
            return False

        except Exception as e:
            self.logger.error(f" insert error: {e}")
            # raise Exception(f"{__name__} insert error: {e}")
            return False

        return True

    async def select(self, item_id):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = self.table.select(self.table.c.id == item_id)
                result = await conn.execute(stmt)
                ans = []
                for row in result.mappings():
                    ans.append(self.entity(**row))

        except Exception as e:
            self.logger.error(e)
            raise Exception(f"{__name__} select error")
            # return []

        return ans


    async def select_by(self, **filters):
        """

            조건 조회

            select_by(user_id=5, status='active')
            -> SELECT * FROM table WHERE user_id = 5 AND phone = '01012341234'

        """
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = self.table.select()

                for column, value in filters.items():
                    if hasattr(self.table.c, column):
                        stmt = stmt.where(getattr(self.table.c, column) == value)

                result = await conn.execute(stmt)
                ans = []
                for row in result.mappings():
                    ans.append(self.entity(**row))
        except Exception as e:
            self.logger.error(e)
            return []

        return ans


    async def update(self, item_id, item):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = self.table.update().values(**item).where(self.table.c.id == item_id)
                await conn.execute(stmt)
        except Exception as e:
            self.logger.error(e)
            raise Exception(f"{__name__} update error")
            # return False

        return True

    async def delete(self, item_id):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = self.table.delete().where(self.table.c.id == item_id)
                result = await conn.execute(stmt)

                if result.rowcount == 0:
                    self.logger.warning(f"No record found with id: {item_id}")
                    return False

        except Exception as e:
            self.logger.error(e)
            raise Exception(f"{__name__} delete error")

        return True

