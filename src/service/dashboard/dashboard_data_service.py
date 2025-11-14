from sqlalchemy import func, select
from typing import List, Dict

from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.maria_engine import get_engine
from src.infra.database.tables.table_category import category_table
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


class DashboardDataService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.category_repo = CategoryRepository()

    async def get_district_stats(self) -> List[Dict]:
        """
        서울특별시 자치구별 매장 수를 집계하여 반환
        
        Returns:
            List[Dict]: [{'gu': '강남구', '음식점': 268, '카페': 124, '콘텐츠': 86}, ...]
        """
        try:
            self.logger.info("자치구별 매장 수 집계 시작")
            engine = await get_engine()
            
            async with engine.connect() as conn:
                # 서울시 자치구 목록 (25개)
                seoul_gu_list = [
                    '강남구', '강동구', '강서구', '강북구', '관악구', '광진구', '구로구', '금천구',
                    '노원구', '동대문구', '도봉구', '동작구', '마포구', '서대문구', '성동구', '성북구',
                    '서초구', '송파구', '영등포구', '용산구', '양천구', '은평구', '종로구', '중구', '중랑구'
                ]
                
                # 각 자치구별로 type별 매장 수 집계
                result = []
                
                for gu in seoul_gu_list:
                    # type별 집계 쿼리
                    # type: 1 = 음식점, 2 = 카페, 3 = 콘텐츠
                    # si 조건 제거 (데이터에 따라 다를 수 있음)
                    stmt = select(
                        category_table.c.type,
                        func.count(category_table.c.id).label('count')
                    ).where(
                        category_table.c.gu == gu
                    ).group_by(category_table.c.type)
                    
                    query_result = await conn.execute(stmt)
                    rows = query_result.fetchall()
                    self.logger.debug(f"{gu} 조회 결과: {len(rows)}개 type")
                    
                    # 초기값 설정
                    gu_data = {
                        'gu': gu,
                        '음식점': 0,
                        '카페': 0,
                        '콘텐츠': 0
                    }
                    
                    # type별 카운트 매핑
                    # type: '1' = 음식점, '2' = 카페, '3' = 콘텐츠 (String(1)로 저장됨)
                    for row in rows:
                        type_value = str(row.type) if row.type else None
                        count = row.count
                        
                        if type_value == '1':
                            gu_data['음식점'] = count
                        elif type_value == '2':
                            gu_data['카페'] = count
                        elif type_value == '3':
                            gu_data['콘텐츠'] = count
                    
                    result.append(gu_data)
                
                self.logger.info(f"자치구별 매장 수 집계 완료: {len(result)}개 구")
                return result
                
        except Exception as e:
            error_msg = f"자치구별 매장 수 집계 오류: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            # 데이터베이스 연결 오류인 경우 더 자세한 정보 제공
            if "engine error" in str(e).lower() or "connection" in str(e).lower():
                raise Exception(f"데이터베이스 연결 오류가 발생했습니다. 데이터베이스 서버가 실행 중인지 확인하세요. 원본 오류: {str(e)}")
            raise Exception(error_msg) from e

