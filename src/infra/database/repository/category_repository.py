from sqlalchemy import func, select

from src.domain.dto.category.category_dto import CategoryListItemDTO
from src.domain.entities.category_entity import CategoryEntity
from src.infra.database.repository import base_repository
from src.infra.database.repository.maria_engine import get_engine
from src.infra.database.tables.table_category import category_table


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

    #   매장 별 리뷰 수, 별점 평균
    async def get_review_statistics(
            self,
            is_random: int = 0,              #   0 random
            limit: int = None,
            **filters
    ) -> list[CategoryListItemDTO]:
        from src.infra.database.tables.table_reviews import reviews_table

        engine = await get_engine()
        async with engine.begin() as conn:
            # 주소 조합
            full_address = func.trim(
                func.concat_ws(' ',
                               func.nullif(self.table.c.do, ''),
                               func.nullif(self.table.c.si, ''),
                               func.nullif(self.table.c.gu, ''),
                               func.nullif(self.table.c.detail_address, '')
                               )
            ).label('detail_address')

            # 기본 쿼리
            stmt = select(
                func.count().label('review_count'),
                func.avg(reviews_table.c.stars).label('average_stars'),
                self.table.c.id.label('id'),
                self.table.c.name.label("title"),
                self.table.c.image.label("image_url"),
                full_address,
                self.table.c.sub_category.label("sub_category"),
                self.table.c.type.label('type'),
                self.table.c.latitude.label('lat'),
                self.table.c.longitude.label('lng'),
            )

            if is_random:
                stmt = stmt.select_from(
                    self.table.join(
                        reviews_table,
                        reviews_table.c.category_id == self.table.c.id
                    )
                )
            else:
                stmt = stmt.select_from(
                    self.table.outerjoin(
                        reviews_table,
                        reviews_table.c.category_id == self.table.c.id
                    )
                )


            for column, value in filters.items():
                if not hasattr(self.table.c, column):
                    continue

                col = getattr(self.table.c, column)

                if isinstance(value, list):
                    stmt = stmt.where(col.in_(value))
                else:
                    stmt = stmt.where(col == value)

            # GROUP BY
            if is_random == 0:
                stmt = stmt.group_by(self.table.c.id).order_by(func.rand())
            else:
                stmt = stmt.group_by(self.table.c.id)

            if limit:
                stmt = stmt.limit(limit)


            # 실행
            result = await conn.execute(stmt)
            rows = list(result.mappings())

        # DTO 변환
        return [CategoryListItemDTO(**row) for row in rows]
