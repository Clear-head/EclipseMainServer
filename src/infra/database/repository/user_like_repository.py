from sqlalchemy import select, func

from src.domain.dto.like.like_dto import LikeItemDTO
from src.domain.entities.user_like_entity import UserLikeEntity
from src.infra.database.repository import base_repository
from src.infra.database.repository.maria_engine import get_engine
from src.infra.database.tables.table_user_like import user_like_table


class UserLikeRepository(base_repository.BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = user_like_table
        self.entity = UserLikeEntity

    async def insert(self, item):
        return await super().insert(item)

    async def select(self, **filters):
        return await super().select(**filters)

    async def update(self, item_id, item):
        return await super().update(item_id, item)

    async def delete(self, **filters):
        return await super().delete(**filters)

    async def get_user_likes_with_review_stats(self, user_id: str) -> list[LikeItemDTO]:
        """
        사용자의 좋아요 목록을 리뷰 통계와 함께 조회합니다.
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            list[LikeItemDTO]: 리뷰 통계가 포함된 좋아요 목록
        """
        from src.infra.database.tables.table_category import category_table
        from src.infra.database.tables.table_reviews import reviews_table

        engine = await get_engine()
        async with engine.begin() as conn:
            # Build query with LEFT JOIN to reviews and aggregation
            stmt = select(
                category_table.c.type.label('type'),
                category_table.c.id.label('category_id'),
                category_table.c.name.label('category_name'),
                category_table.c.image.label('category_image'),
                category_table.c.sub_category.label('sub_category'),
                category_table.c.do.label('do'),
                category_table.c.si.label('si'),
                category_table.c.gu.label('gu'),
                category_table.c.detail_address.label('detail_address'),
                func.count(reviews_table.c.id).label('review_count'),
                func.coalesce(func.avg(reviews_table.c.stars), 0.0).label('average_rating')
            ).select_from(
                self.table.join(
                    category_table,
                    self.table.c.category_id == category_table.c.id
                ).outerjoin(
                    reviews_table,
                    reviews_table.c.category_id == category_table.c.id
                )
            ).where(
                self.table.c.user_id == user_id
            ).group_by(
                category_table.c.id,
                category_table.c.type,
                category_table.c.name,
                category_table.c.image,
                category_table.c.sub_category,
                category_table.c.do,
                category_table.c.si,
                category_table.c.gu,
                category_table.c.detail_address
            )
            
            result = await conn.execute(stmt)
            rows = list(result.mappings())
            
            if not rows:
                return []
            
            # Convert to DTOs
            return [LikeItemDTO(**row) for row in rows]
