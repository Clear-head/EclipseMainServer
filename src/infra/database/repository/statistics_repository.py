from sqlalchemy import text

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

    async def get_total_users(self) -> dict:
        try:
            self.logger.info("총 사용자 수를 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT COUNT(*) AS total_users
                             FROM users
                             """)

                result = await conn.execute(query)
                row = result.mappings().first()

                return {"total_users": int(row["total_users"] or 0)}

        except Exception as e:
            self.logger.error(f"총 사용자 수 조회 오류: {e}")
            raise e

    async def get_recommendation_stats(self) -> list:
        try:
            self.logger.info("일정표 생성 수 통계를 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT 
                                    DATE(visited_at) AS visited_date,
                                    COUNT(*) AS count
                             FROM user_history
                             WHERE visited_at >= DATE_SUB(CURDATE(), INTERVAL 5 DAY)
                             GROUP BY DATE(visited_at)
                             ORDER BY visited_date
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "visited_date": str(row["visited_date"]),
                        "count": int(row["count"] or 0)
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"일정표 생성 수 통계 조회 오류: {e}")
            raise e

    async def get_weekly_average_stats(self) -> list:
        try:
            self.logger.info("요일별 평균 일정표 생성 수 통계를 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT 
                                    weekday_kor,
                                    ROUND(AVG(cnt), 0) AS avg_per_week
                             FROM (
                                 SELECT
                                     WEEK(visited_at) AS week_num,
                                     CASE DAYOFWEEK(visited_at)
                                         WHEN 1 THEN '일'
                                         WHEN 2 THEN '월'
                                         WHEN 3 THEN '화'
                                         WHEN 4 THEN '수'
                                         WHEN 5 THEN '목'
                                         WHEN 6 THEN '금'
                                         WHEN 7 THEN '토'
                                     END AS weekday_kor,
                                     COUNT(*) AS cnt
                                 FROM user_history
                                 GROUP BY WEEK(visited_at), DAYOFWEEK(visited_at)
                             ) AS sub
                             GROUP BY weekday_kor
                             ORDER BY FIELD(weekday_kor, '월','화','수','목','금','토','일')
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "weekday_kor": row["weekday_kor"] or "",
                        "avg_per_week": int(row["avg_per_week"] or 0)
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"요일별 평균 일정표 생성 수 통계 조회 오류: {e}")
            raise e

    async def get_popular_categories(self) -> list:
        try:
            self.logger.info("인기 카테고리 통계를 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT 
                                    c.type AS category_type,
                                    COUNT(*) AS total_count,
                                    ROUND(COUNT(*) * 100.0 / (
                                        SELECT COUNT(*) 
                                        FROM user_history
                                    ), 1) AS percentage
                             FROM user_history uh
                             JOIN category c
                                 ON uh.category_id = c.id
                             GROUP BY c.type
                             ORDER BY total_count DESC
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "category_type": row["category_type"] or "",
                        "total_count": int(row["total_count"] or 0),
                        "percentage": float(row["percentage"] or 0)
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"인기 카테고리 통계 조회 오류: {e}")
            raise e

    async def get_popular_districts(self) -> list:
        try:
            self.logger.info("일정표 생성 기준 인기 지역 통계를 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT 
                                    c.gu AS district,
                                    COUNT(*) AS total_count
                             FROM user_history uh
                             JOIN category c
                                 ON uh.category_id = c.id
                             GROUP BY c.gu
                             ORDER BY total_count DESC
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "district": row["district"] or "",
                        "total_count": int(row["total_count"] or 0)
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"인기 지역 통계 조회 오류: {e}")
            raise e

    async def get_template_stats(self) -> list:
        try:
            self.logger.info("일정 템플릿 통계를 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT 
                                    template_type,
                                    COUNT(*) AS total_count,
                                    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM merge_history), 1) AS percentage
                             FROM merge_history
                             GROUP BY template_type
                             ORDER BY template_type ASC
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "template_type": row["template_type"] or "",
                        "total_count": int(row["total_count"] or 0),
                        "percentage": float(row["percentage"] or 0)
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"일정 템플릿 통계 조회 오류: {e}")
            raise e

    async def get_transportation_stats(self) -> list:
        try:
            self.logger.info("이동수단 통계를 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT
                                    transportation,
                                    COUNT(*) AS total_count,
                                    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM user_history), 1) AS percentage
                             FROM user_history
                             GROUP BY transportation
                             ORDER BY transportation
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "transportation": row["transportation"] or "",
                        "total_count": int(row["total_count"] or 0),
                        "percentage": float(row["percentage"] or 0)
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"이동수단 통계 조회 오류: {e}")
            raise e