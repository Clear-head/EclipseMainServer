from sqlalchemy import insert, select, update, delete
from sqlalchemy.sql.functions import user

from src.domain.entities.user_entity import UserEntity
from mysql_engine import get_engine
from ..tables.table_users import users_table
from logging import getLogger


class UserRepository:
    def __init__(self):
        self.logger = getLogger("User")
        self.table = users_table


    async def create(self, item):
        """

            회원 가입

        """
        try:
            engine = await get_engine()
            async with engine.begin() as conn:

                stmt = insert(self.table).values(**item)
                await conn.execute(stmt)

        except Exception as e:
            self.logger.error(e)
            return False

        return True


    async def select_id(self, user_id: str):
        """

            아이디 중복 체크

        """
        result = None
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = select(users_table.c.id).where(users_table.c.id == user_id)

                result = await conn.execute(stmt)
                result = result.first()

        except Exception as e:
            self.logger.error(e)
            return Exception("[UserRepository] select error")

        return result is not None

    async def get_user_info(self, user_id: str):
        """

            하루가 쓸 정보

        """
        result = None
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = select(users_table.c).where(users_table.c.id == user_id)
                result = await conn.execute(stmt)
                user_entity = user.UserEntity(**result.one())

        except Exception as e:
            self.logger.error(e)
            return Exception("[UserRepository] select error")

        return user_entity



    async def update(self, item):
        """

            회원 정보 수정

        """
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = update(users_table).values(**item).where(users_table.c.id == item.id)
                await conn.execute(stmt)
        except Exception as e:
            self.logger.error(e)
            return Exception("[UserRepository] update error")
        return True


    async def delete(self):
        """

            회원 탈퇴

        """
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = delete(users_table).where(users_table.c.id == self.table.id)
                await conn.execute(stmt)
        except Exception as e:
            self.logger.error(e)
            raise Exception("[UserRepository] delete error")

        return True
