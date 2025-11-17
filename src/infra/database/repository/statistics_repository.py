from datetime import datetime
from sqlalchemy import text

from src.infra.database.repository.base_repository import BaseRepository
from src.infra.database.repository.maria_engine import get_engine
from src.infra.database.tables.table_delete import delete_cause_table
from src.infra.database.tables.table_users import users_table
from src.infra.database.tables.table_user_history import user_history_table
from src.infra.database.tables.table_report import report_table


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
                             FROM merge_history
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
                                 FROM merge_history
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
                                    COUNT(DISTINCT uh.merge_id) AS total_count
                             FROM user_history uh
                             JOIN category c
                                 ON uh.category_id = c.id
                             GROUP BY c.gu
                             ORDER BY total_count DESC;
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

    async def get_daily_travel_time_stats(self) -> list:
        try:
            self.logger.info("일별 평균 이동 시간 통계를 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT 
                                    DATE(visited_at) AS date,
                                    ROUND(AVG(duration)/60, 1) AS avg_duration,
                                    ROUND(
                                        (AVG(duration)/60) - (
                                            SELECT IFNULL(ROUND(AVG(duration)/60, 1), 0)
                                            FROM user_history
                                            WHERE visited_at >= DATE_SUB(DATE(uh.visited_at), INTERVAL 7 DAY)
                                            AND visited_at < DATE(uh.visited_at)
                                        ), 1
                                    ) AS weekly_diff
                             FROM user_history uh
                             WHERE visited_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                             GROUP BY DATE(visited_at)
                             ORDER BY date DESC
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "date": str(row["date"]),
                        "avg_duration": float(row["avg_duration"] or 0),
                        "weekly_diff": float(row["weekly_diff"] or 0)
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"일별 평균 이동 시간 통계 조회 오류: {e}")
            raise e

    async def get_total_travel_time_avg(self) -> dict:
        try:
            self.logger.info("전체 이동 평균 시간을 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT ROUND(AVG(duration)/60, 1) AS avg_duration
                             FROM user_history
                             """)

                result = await conn.execute(query)
                row = result.mappings().first()

                return {"avg_duration": float(row["avg_duration"] or 0)}

        except Exception as e:
            self.logger.error(f"전체 이동 평균 시간 조회 오류: {e}")
            raise e

    async def get_transportation_travel_time_avg(self) -> list:
        try:
            self.logger.info("이동수단별 평균 이동 시간을 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT 
                                    transportation,
                                    CASE 
                                        WHEN transportation = 0 OR transportation = '0' THEN '도보'
                                        WHEN transportation = 1 OR transportation = '1' THEN '대중교통'
                                        WHEN transportation = 2 OR transportation = '2' THEN '자동차'
                                        ELSE transportation
                                    END AS type_name,
                                    ROUND(AVG(duration) / 60, 1) AS avg_minutes
                             FROM user_history
                             WHERE transportation IS NOT NULL
                             GROUP BY transportation
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "transportation": str(row["transportation"]) if row["transportation"] is not None else "",
                        "type_name": row["type_name"] or "",
                        "avg_minutes": float(row["avg_minutes"] or 0)
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"이동수단별 평균 이동 시간 조회 오류: {e}")
            raise e

    async def get_delete_cause_stats(self) -> list:
        try:
            self.logger.info("계정 삭제 이유 통계를 조회합니다.")
            # base_repository.select() 사용을 위해 임시로 테이블 설정
            original_table = self.table
            self.table = delete_cause_table
            
            # base_repository.select() 사용 (ORDER BY count DESC)
            # return_dto를 사용하여 rows를 그대로 반환받음 (base_repository.py 수정 없이)
            rows = await self.select(
                return_dto=lambda **kwargs: kwargs,  # 딕셔너리를 그대로 반환하는 람다 함수
                columns=['cause', 'count'],
                order='count'  # 문자열로 전달하면 내부에서 desc()로 처리됨
            )
            
            # 테이블 원복
            self.table = original_table
            
            return [
                {
                    "cause": row["cause"] or "",
                    "count": int(row["count"] or 0)
                }
                for row in rows
            ]

        except Exception as e:
            self.logger.error(f"계정 삭제 이유 통계 조회 오류: {e}")
            raise e

    async def get_general_inquiries(self) -> list:
        try:
            self.logger.info("일반 문의 사항을 조회합니다.")
            # base_repository.select() 사용을 위해 임시로 테이블 설정
            original_table = self.table
            self.table = report_table
            
            # base_repository.select() 사용 (WHERE type=3, ORDER BY reported_at DESC)
            # return_dto를 사용하여 rows를 그대로 반환받음 (base_repository.py 수정 없이)
            rows = await self.select(
                return_dto=lambda **kwargs: kwargs,  # 딕셔너리를 그대로 반환하는 람다 함수
                columns=['id', 'reporter', 'cause', 'reported_at', 'is_processed'],
                type=3,
                order='reported_at'  # 문자열로 전달하면 내부에서 desc()로 처리됨
            )
            
            # 테이블 원복
            self.table = original_table
            
            return [
                {
                    "id": int(row["id"] or 0),
                    "reporter": row["reporter"] or "",
                    "cause": row["cause"] or "" if row.get("cause") else "",
                    "reported_at": str(row["reported_at"]) if row.get("reported_at") else "",
                    "is_processed": 1 if row.get("is_processed") else 0  # Boolean을 int로 변환
                }
                for row in rows
            ]

        except Exception as e:
            self.logger.error(f"일반 문의 사항 조회 오류: {e}")
            raise e

    async def get_report_inquiries(self) -> list:
        try:
            self.logger.info("신고 문의 사항을 조회합니다.")
            # base_repository.select() 사용을 위해 임시로 테이블 설정
            original_table = self.table
            self.table = report_table
            
            # base_repository.select() 사용 (WHERE type IN (0,1,2), ORDER BY reported_at DESC)
            # base_repository.select()는 리스트를 IN 절로 처리함
            # return_dto를 사용하여 rows를 그대로 반환받음 (base_repository.py 수정 없이)
            rows = await self.select(
                return_dto=lambda **kwargs: kwargs,  # 딕셔너리를 그대로 반환하는 람다 함수
                columns=['id', 'reporter', 'type', 'cause', 'reported_at', 'is_processed'],
                type=[0, 1, 2],  # 리스트로 전달하면 IN 절로 처리됨
                order='reported_at'  # 문자열로 전달하면 내부에서 desc()로 처리됨
            )
            
            # 테이블 원복
            self.table = original_table
            
            # type 매핑: 0=채팅, 1=게시글, 2=댓글
            type_map = {
                0: "채팅",
                1: "게시글",
                2: "댓글"
            }

            return [
                {
                    "id": int(row["id"] or 0),
                    "reporter": row["reporter"] or "",
                    "type": int(row["type"] or 0),
                    "type_name": type_map.get(int(row["type"] or 0), "기타"),
                    "cause": row["cause"] or "" if row.get("cause") else "",
                    "reported_at": str(row["reported_at"]) if row.get("reported_at") else "",
                    "is_processed": 1 if row.get("is_processed") else 0  # Boolean을 int로 변환
                }
                for row in rows
            ]

        except Exception as e:
            self.logger.error(f"신고 문의 사항 조회 오류: {e}")
            raise e

    async def get_account_and_report_status(self) -> list:
        try:
            self.logger.info("계정 및 신고 현황을 조회합니다.")
            engine = await get_engine()
            async with engine.begin() as conn:
                query = text("""
                             SELECT
                                u.id AS user_id,
                                CASE
                                    WHEN b.user_id IS NOT NULL THEN '제한'
                                    ELSE '활성'
                                END AS account_status,
                                GROUP_CONCAT(r.cause ORDER BY r.reported_at DESC SEPARATOR ', ') AS recent_reports
                            FROM users u
                            LEFT JOIN black b
                                ON u.id = b.user_id
                            LEFT JOIN report r
                                ON u.id = r.user_id
                                AND r.type <> 3    
                            GROUP BY u.id, account_status
                            ORDER BY u.id
                             """)

                result = await conn.execute(query)
                rows = result.mappings().all()

                return [
                    {
                        "user_id": row["user_id"] or "",
                        "account_status": row["account_status"] or "활성",
                        "recent_reports": row["recent_reports"] or "없음",
                        "report_count": len(row["recent_reports"].split(", ")) if row.get("recent_reports") and row["recent_reports"] != "없음" else 0
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"계정 및 신고 현황 조회 오류: {e}")
            raise e

    async def get_user_count(self) -> int:
        """
        총 유저 수를 조회합니다.
        
        Returns:
            int: 총 유저 수
        """
        try:
            self.logger.info("총 유저 수를 조회합니다.")
            # base_repository.select() 사용을 위해 임시로 테이블 설정
            original_table = self.table
            self.table = users_table
            
            # base_repository.select() 사용
            # return_dto를 사용하여 rows를 그대로 반환받음 (base_repository.py 수정 없이)
            rows = await self.select(return_dto=lambda **kwargs: kwargs, columns=['id'])
            
            # 테이블 원복
            self.table = original_table
            
            return len(rows)

        except Exception as e:
            self.logger.error(f"총 유저 수 조회 오류: {e}")
            raise e

    async def get_history_count(self, visited_at: datetime = None) -> list:
        """
        날짜별 템플릿 작성 수를 조회합니다.
        
        Args:
            visited_at: 조회할 날짜 (None이면 전체)
        
        Returns:
            list: 조회된 히스토리 리스트
        """
        try:
            self.logger.info("날짜별 템플릿 작성 수를 조회합니다.")
            # base_repository.select() 사용을 위해 임시로 테이블 설정
            original_table = self.table
            self.table = user_history_table
            
            # base_repository.select() 사용
            # return_dto를 사용하여 rows를 그대로 반환받음 (base_repository.py 수정 없이)
            if visited_at is None:
                rows = await self.select(return_dto=lambda **kwargs: kwargs, columns=['id'])
            else:
                rows = await self.select(return_dto=lambda **kwargs: kwargs, columns=['id'], visited_at=visited_at)
            
            # 테이블 원복
            self.table = original_table
            
            return rows

        except Exception as e:
            self.logger.error(f"날짜별 템플릿 작성 수 조회 오류: {e}")
            raise e