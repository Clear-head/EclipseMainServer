from sqlalchemy import select
from . import base_repository
from .maria_engine import get_engine
from ..tables.table_users import users_table
from src.domain.entities.user_entity import UserEntity


class UserRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = users_table
        self.entity = UserEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, item, limit=None):
        return await super().select(item, limit=limit)

    async def update(self, item_id, item):
        return await super().update(item_id, item)

    async def delete(self, item):
        return await super().delete(item)

    async def select_by(self, **filters):
        return await super().select_by(**filters)


    async def get_user_info(self, user_id: str):
        """

                                하루가 쓸 정보

        """
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = select(self.table.c).where(self.table.c.id == user_id)
                result = await conn.execute(stmt)
                user_entity = self.entity(**result.one())
        except Exception as e:
            self.logger.error(e)
            raise Exception("[UserRepository] select error") from e

        return user_entity


# do: 이거 서비스 레이어로 옮기기
# async def duplicate_check_id(self, user_id: str):
#     """
#
#         아이디 중복 체크
#
#     """
#     result = None
#     try:
#         engine = await get_engine()
#         async with engine.begin() as conn:
#             stmt = select(self.table.c.id).where(self.table.c.id == user_id)
#
#             result = await conn.execute(stmt)
#             result = result.first()
#
#     except Exception as e:
#         self.logger.error(e)
#         return Exception("[UserRepository] select error")
#
#     return result is not None