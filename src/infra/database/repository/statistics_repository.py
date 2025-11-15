from sqlalchemy import select, func, text

from src.infra.database.repository.base_repository import BaseRepository
from src.infra.database.repository.maria_engine import get_engine


class StatisticsRepository(BaseRepository):
    def __init__(self):
        super(StatisticsRepository, self).__init__()
        self.table = None
        self.entity = None

    async def get_tag_statistics(self, category_type: str) -> list:
        try:
            self.logger.info("카테고리 타입별 태그 통계를 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT t.name,
                                    SUM(ct.count) AS total_count
                             FROM category_tags ct
                                      INNER JOIN tags t ON ct.tag_id = t.id
                                      INNER JOIN category c ON ct.category_id = c.id
                             WHERE c.type = :category_type
                             GROUP BY t.id, t.name
                             ORDER BY total_count DESC LIMIT 10
                             """)

                result = await conn.execute(query, {"category_type": category_type})
                rows = result.mappings().all()

                return [{"name": row["name"], "total_count": int(row["total_count"])} for row in rows]

        except Exception as e:
            self.logger.error(f"태그 통계 조회 오류: {e}")
            raise e


    async def get_popular_places(self) -> list:
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT c.name         AS 이름,
                                    c.gu           AS 구,
                                    c.sub_category AS 서브카테고리,
                                    c.menu         AS 메뉴
                             FROM category AS c
                                      LEFT JOIN
                                  user_history AS u
                                  ON u.category_id = c.name
                             GROUP BY c.name, c.gu, c.sub_category, c.menu
                             ORDER BY COUNT(u.category_id) DESC LIMIT 10
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "이름": row["이름"] or "",
                        "구": row["구"] or "",
                        "서브카테고리": row["서브카테고리"] or "",
                        "메뉴": row["메뉴"] or ""
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"인기 장소 조회 오류: {e}")
            raise e


    async def get_district_stats(self) -> list:
        try:
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT c.gu,
                                    SUM(CASE WHEN c.type = '0' THEN 1 ELSE 0 END) AS 음식점,
                                    SUM(CASE WHEN c.type = '1' THEN 1 ELSE 0 END) AS 카페,
                                    SUM(CASE WHEN c.type = '2' THEN 1 ELSE 0 END) AS 콘텐츠
                             FROM category c
                             WHERE c.si = '서울특별시'
                               AND c.gu IS NOT NULL
                               AND c.gu != ''
                             GROUP BY c.gu
                             ORDER BY c.gu
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "gu": row["gu"] or "",
                        "음식점": int(row["음식점"] or 0),
                        "카페": int(row["카페"] or 0),
                        "콘텐츠": int(row["콘텐츠"] or 0)
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"구별 통계 조회 오류: {e}")
            raise e
