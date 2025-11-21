from src.infra.database.repository.statistics_repository import StatisticsRepository
from src.logger.custom_logger import get_logger


class DashboardUserService:
    def __init__(self):
        self.logger = get_logger(__name__)

    async def get_delete_cause_stats(self) -> list:
        """
        계정 삭제 이유 통계를 조회합니다.
        
        Returns:
            list: [{'cause': '기록 삭제 목적', 'count': 38}, ...]
        """
        try:
            self.logger.info("계정 삭제 이유 통계를 조회")
            return await StatisticsRepository().get_delete_cause_stats()
        except Exception as e:
            self.logger.error(f"계정 삭제 이유 통계 조회 오류: {e}")
            raise e

    async def get_general_inquiries(self) -> list:
        """
        일반 문의 사항을 조회합니다.
        
        Returns:
            list: [{'id': 1, 'reporter': 'user001', 'cause': '문의 내용', 'reported_at': '2025-11-04 14:23', 'is_processed': 0}, ...]
        """
        try:
            self.logger.info("일반 문의 사항을 조회")
            return await StatisticsRepository().get_general_inquiries()
        except Exception as e:
            self.logger.error(f"일반 문의 사항 조회 오류: {e}")
            raise e

    async def get_report_inquiries(self) -> list:
        """
        신고 문의 사항을 조회합니다.
        
        Returns:
            list: [{'id': 1, 'reporter': 'user045', 'type': 0, 'type_name': '채팅', 'cause': '스팸/광고', 'reported_at': '2025-11-04 08:15', 'is_processed': 0}, ...]
        """
        try:
            self.logger.info("신고 문의 사항을 조회")
            return await StatisticsRepository().get_report_inquiries()
        except Exception as e:
            self.logger.error(f"신고 문의 사항 조회 오류: {e}")
            raise e

    async def get_account_and_report_status(self) -> list:
        """
        신고 현황을 조회합니다.
        
        Returns:
            list: [{'user_id': 'user001', 'account_status': '활성', 'recent_reports': '스팸/광고, 욕설/비방'}, ...]
        """
        try:
            self.logger.info("신고 현황을 조회")
            return await StatisticsRepository().get_account_and_report_status()
        except Exception as e:
            self.logger.error(f"신고 현황 조회 오류: {e}")
            raise e

