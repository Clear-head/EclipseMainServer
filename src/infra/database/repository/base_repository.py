from sqlalchemy import insert, select, update, delete, join, and_
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

    from sqlalchemy import select, join, and_

    async def select_with_join(
            self,
            user_id,
            join_table,
            dto,
            join_conditions: dict,
            select_columns: dict = None,
            **filters
    ) -> list:
        """
        select_columns 예시:
        {
            'main': ['category_id'],
            'join': ['name', 'type']  # list면 join_ 접두사
            or
            'join': {'name': 'category_name', 'type': 'category_type'}  # dict면 커스텀 별칭
        }
        """
        ans = []
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                # 조인 생성
                j = self._build_join(join_table, join_conditions)

                # SELECT 컬럼 생성
                selected = self._build_select_columns(join_table, select_columns)

                # 기본 쿼리 생성
                stmt = self._build_base_statement(selected, j, user_id)

                # 필터 적용
                stmt = self._apply_filters(stmt, filters)

                # 실행 및 결과 처리
                result = await conn.execute(stmt)
                rows = list(result.mappings())

                if not rows:
                    self.logger.info(f"no items found in {self.table}")
                else:
                    ans = [dto(**row) for row in rows]

        except Exception as e:
            self.logger.error(f"select with join {self.table}, {join_table} error: {e}")
            raise e

        return ans


    #   join 객체
    def _build_join(self, join_table, join_conditions: dict):
        if not join_conditions:
            raise ValueError("조인문 조건 없음")

        join_conditions_list = []
        for left_col, right_col in join_conditions.items():
            if hasattr(self.table.c, left_col) and hasattr(join_table.c, right_col):
                join_conditions_list.append(
                    getattr(self.table.c, left_col) == getattr(join_table.c, right_col)
                )

        if not join_conditions_list:
            raise ValueError("유효한 조인 조건이 없음")

        return join(self.table, join_table, and_(*join_conditions_list))


    #   select 에 * 말고 ~~~ 달기
    def _build_select_columns(self, join_table, select_columns: dict = None) -> list:
        if select_columns is None:
            return [self.table]

        selected = []

        # main 테이블 컬럼
        if 'main' in select_columns:
            for col in select_columns['main']:
                if hasattr(self.table.c, col):
                    selected.append(getattr(self.table.c, col))

        # join 테이블 컬럼
        if 'join' in select_columns:
            join_cols = select_columns['join']

            if isinstance(join_cols, dict):

                # dict: {DB컬럼명: DTO필드명}
                for db_col, dto_field in join_cols.items():
                    if hasattr(join_table.c, db_col):
                        selected.append(
                            getattr(join_table.c, db_col).label(dto_field)
                        )

            elif isinstance(join_cols, list):

                # list: DB컬럼명 그대로, join_ 접두사 추가
                for col in join_cols:
                    if hasattr(join_table.c, col):
                        selected.append(
                            getattr(join_table.c, col).label(f'join_{col}')
                        )

        return selected

    #   select *
    def _build_base_statement(self, selected, join_obj, user_id):
        return (
            select(*selected)
            .select_from(join_obj)
            .where(self.table.c.id == user_id)
        )

    #   where 절 생성
    def _apply_filters(self, stmt, filters: dict):
        for column, value in filters.items():
            if hasattr(self.table.c, column):
                stmt = stmt.where(getattr(self.table.c, column) == value)
        return stmt

