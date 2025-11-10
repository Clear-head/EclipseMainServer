from sqlalchemy import func

from src.domain.entities.category_entity import CategoryEntity
from src.infra.database.repository import base_repository
from src.infra.database.tables.table_category import category_table
from src.infra.database.repository.maria_engine import get_engine


class CategoryRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = category_table
        self.entity = CategoryEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, **filters):
        return await super().select(**filters)
        
    async def update(self, item_id, item):
        return await super().update(item_id, item)
        
    async def delete(self, **filters):
        return await super().delete(**filters)
    
    async def select_random(self, limit=10, **filters):
        """
        랜덤 조회 (카테고리 필터만 적용)
        
        사용 예시:
        categories = await repo.select_random(
            limit=10,
            type='0'
        )
        """
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                # SELECT 문 생성
                stmt = base_repository.select(self.table).select_from(self.table)
                
                # WHERE 절 추가
                for column, value in filters.items():
                    if not hasattr(self.table.c, column):
                        continue
                    
                    col = getattr(self.table.c, column)
                    
                    if isinstance(value, list):
                        stmt = stmt.where(col.in_(value))
                    else:
                        stmt = stmt.where(col == value)
                
                # ORDER BY RANDOM() (MariaDB/MySQL에서는 RAND())
                stmt = stmt.order_by(func.rand())
                
                # LIMIT
                if limit is not None:
                    stmt = stmt.limit(limit)
                
                # 실행
                result = await conn.execute(stmt)
                rows = list(result.mappings())
                
                if not rows:
                    self.logger.info(f"no items in {self.table} with filters: {filters}")
                    return []
                
                return [self.entity(**row) for row in rows]
        
        except Exception as e:
            self.logger.error(f"select_random error in {self.table}: {e}")
            raise e
