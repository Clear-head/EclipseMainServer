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
            is_random: bool = True,              #   0 random
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
                func.count(reviews_table.c.id).label('review_count'),
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


    async def get_stores_with_review_stats(
        self,
        limit: int = None,
        **filters
    ) -> list[CategoryListItemDTO]:
        """
        리뷰 통계를 포함한 매장 조회 (리뷰가 없는 매장도 포함 - LEFT JOIN)
        
        사용 예시:
        # ID 리스트로 상세 조회
        stores = await repo.get_stores_with_review_stats(
            id=['id1', 'id2', 'id3']
        )
        """
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

            # LEFT JOIN 쿼리 (리뷰 없는 매장도 포함)
            stmt = select(
                self.table.c.id.label('id'),
                self.table.c.name.label("title"),
                self.table.c.image.label("image_url"),
                full_address,
                self.table.c.sub_category.label("sub_category"),
                self.table.c.latitude.label('lat'),
                self.table.c.longitude.label('lng'),
                func.coalesce(func.count(reviews_table.c.id), 0).label('review_count'),
                func.coalesce(func.avg(reviews_table.c.stars), 0.0).label('average_stars'),
            ).select_from(
                self.table.outerjoin(  # LEFT JOIN
                    reviews_table,
                    reviews_table.c.category_id == self.table.c.id
                )
            )

            # WHERE 절 추가
            for column, value in filters.items():
                if not hasattr(self.table.c, column):
                    continue
                
                col = getattr(self.table.c, column)
                
                if isinstance(value, list):
                    stmt = stmt.where(col.in_(value))
                else:
                    stmt = stmt.where(col == value)

            # GROUP BY
            stmt = stmt.group_by(self.table.c.id)

            # LIMIT
            if limit:
                stmt = stmt.limit(limit)

            # 실행
            result = await conn.execute(stmt)
            rows = list(result.mappings())

            if not rows:
                self.logger.info(f"no items in {self.table} with filters: {filters}")
                return []

            # DTO 변환
            return [CategoryListItemDTO(**row) for row in rows]


    async def get_random_stores_with_reviews(
        self,
        limit: int = 10,
        **filters
    ) -> list[CategoryListItemDTO]:
        """
        리뷰가 있는 매장 중에서 랜덤 조회 (INNER JOIN)
        
        사용 예시:
        stores = await repo.get_random_stores_with_reviews(
            gu='강남구',
            type='0',
            limit=10
        )
        """
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

            # INNER JOIN 쿼리 (리뷰 있는 매장만)
            stmt = select(
                self.table.c.id.label('id'),
                self.table.c.name.label("title"),
                self.table.c.image.label("image_url"),
                full_address,
                self.table.c.sub_category.label("sub_category"),
                self.table.c.latitude.label('lat'),
                self.table.c.longitude.label('lng'),
                func.count(reviews_table.c.id).label('review_count'),
                func.avg(reviews_table.c.stars).label('average_stars'),
            ).select_from(
                self.table.join(  # INNER JOIN
                    reviews_table,
                    reviews_table.c.category_id == self.table.c.id
                )
            )

            # WHERE 절 추가
            for column, value in filters.items():
                if not hasattr(self.table.c, column):
                    continue
                
                col = getattr(self.table.c, column)
                
                if isinstance(value, list):
                    stmt = stmt.where(col.in_(value))
                else:
                    stmt = stmt.where(col == value)

            # GROUP BY + 리뷰 1개 이상 + 랜덤 정렬
            stmt = stmt.group_by(self.table.c.id).having(func.count() >= 1).order_by(func.rand())

            # LIMIT
            if limit:
                stmt = stmt.limit(limit)

            # 실행
            result = await conn.execute(stmt)
            rows = list(result.mappings())

            if not rows:
                self.logger.info(f"no items in {self.table} with filters: {filters}")
                return []

            # DTO 변환
            return [CategoryListItemDTO(**row) for row in rows]