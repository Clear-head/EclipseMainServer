from sqlalchemy import select, join, and_, outerjoin
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
            entity = self.entity(**item.model_dump(exclude_none=True))

            async with engine.begin() as conn:
                data = entity.model_dump()
                stmt = self.table.insert().values(**data)
                await conn.execute(stmt)

            return True

        except IntegrityError as e:
            self.logger.error(f"uuid duplicate error: {e}")
            raise e
        except Exception as e:
            self.logger.error(f"insert error: {e}")
            raise e


    async def select(
            self,
            joins=None,
            columns=None,
            return_dto=None,
            limit=None,
            **filters
    ) -> list:
        """
        # 기본 조회
        users = await repo.select(id='user123')
        users = await repo.select(age=25, city='Seoul')

        # IN 조회 (리스트 전달)
        users = await repo.select(id=['user1', 'user2', 'user3'])

        # 특정 컬럼만
        users = await repo.select(
            columns=['id', 'nickname'],
            age=25
        )

        # JOIN 조회
        reviews = await repo.select(
            joins=[
                {
                    'table': user_table,
                    'on': {'user_id': 'id'},
                    'alias': 'user',
                    'type': 'left'  # optional, default 'inner'
                }
            ],
            columns={
                'id': None,
                'comment': 'review_comment',
                'user.nickname': 'author_name',
                'user.email': None
            },
            category_id='cat123'
        )

        # columns를 list로도 가능 (alias 불필요시)
        reviews = await repo.select(
            joins=[...],
            columns=['id', 'comment', 'user.nickname'],
            category_id='cat123'
        )
        """
        try:
            engine = await get_engine()
            async with engine.begin() as conn:

                # 1. FROM 절 구성
                if joins:
                    from_clause, join_map = self._build_joins(joins)
                else:
                    from_clause = self.table
                    join_map = {}

                # 2. SELECT 절 구성
                if columns:
                    selected = self._build_columns(columns, join_map)
                else:
                    selected = [self.table]

                # 3. 쿼리 생성
                stmt = select(*selected).select_from(from_clause)

                # 4. WHERE 절 추가
                for column, value in filters.items():
                    if not hasattr(self.table.c, column):
                        continue

                    col = getattr(self.table.c, column)

                    # 리스트면 IN 절, 아니면 = 비교
                    if isinstance(value, list):
                        stmt = stmt.where(col.in_(value))
                    else:
                        stmt = stmt.where(col == value)

                # 5. LIMIT
                if limit is not None:
                    stmt = stmt.limit(limit)

                # 6. 실행
                result = await conn.execute(stmt)
                rows = list(result.mappings())

                if not rows:
                    self.logger.info(f"no items in {self.table} with filters: {filters}")
                    return []

                # 7. 반환 형식 결정
                if return_dto:
                    return [return_dto(**row) for row in rows]
                elif not joins:
                    return [self.entity(**row) for row in rows]
                else:
                    return rows

        except Exception as e:
            self.logger.error(f"select error in {self.table}: {e}")
            raise e


    async def update(self, item_id, item):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = (
                    self.table.update()
                    .values(**item.model_dump(exclude_none=True))
                    .where(self.table.c.id == item_id)
                )
                await conn.execute(stmt)
            return True

        except Exception as e:
            self.logger.error(f"update error in {self.table}: {e}")
            raise e


    async def select_by(self, **filters):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = select(self.table)

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


    async def delete(self, **filters):
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                stmt = self.table.delete()
                for column, value in filters.items():
                    if hasattr(self.table.c, column):
                        stmt = stmt.where(getattr(self.table.c, column) == value)
                await conn.execute(stmt)
            return True

        except Exception as e:
            self.logger.error(f"delete error in {self.table}: {e}")
            raise e


    def _build_joins(self, joins: list) -> tuple:
        """
            Returns:
                (join_chain, join_map)
                join_map: {'user': user_table, 'category': category_table}
        """
        current_join = self.table
        join_map = {}

        for join_info in joins:
            join_table = join_info['table']
            alias = join_info.get('alias')
            on_conditions = join_info['on']
            join_type = join_info.get('type', 'inner')

            # alias 저장
            if alias:
                join_map[alias] = join_table

            # JOIN 조건 생성
            conditions = []
            for left_col, right_col in on_conditions.items():
                left = getattr(current_join.c, left_col)
                right = getattr(join_table.c, right_col)
                conditions.append(left == right)

            # JOIN 실행
            if join_type == 'left':
                current_join = outerjoin(current_join, join_table, and_(*conditions))
            else:
                current_join = join(current_join, join_table, and_(*conditions))

        return current_join, join_map

    def _build_columns(self, columns, join_map: dict) -> list:
        """
            columns 형식:
            1. list: ['id', 'name', 'user.nickname']
            2. dict: {'id': None, 'name': 'category_name', 'user.nickname': 'author'}
        """
        selected = []

        # list 형식
        if isinstance(columns, list):
            for col_str in columns:
                col = self._parse_column(col_str, join_map)
                selected.append(col)

        # dict 형식 (alias 지정 가능)
        elif isinstance(columns, dict):
            for col_str, alias in columns.items():
                col = self._parse_column(col_str, join_map)

                if alias:
                    selected.append(col.label(alias))
                else:
                    selected.append(col)

        return selected

    def _parse_column(self, col_str: str, join_map: dict):
        """
            'user.nickname' → user_table.c.nickname
            'id' → self.table.c.id
        """
        if '.' in col_str:
            alias, col_name = col_str.split('.', 1)

            if alias not in join_map:
                raise ValueError(f"Unknown alias: '{alias}'. Available: {list(join_map.keys())}")

            table = join_map[alias]

            if not hasattr(table.c, col_name):
                raise ValueError(f"Column '{col_name}' not found in table '{alias}'")

            return getattr(table.c, col_name)
        else:
            if not hasattr(self.table.c, col_str):
                raise ValueError(f"Column '{col_str}' not found in main table")

            return getattr(self.table.c, col_str)