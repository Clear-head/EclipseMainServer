"""
크롤링 스케줄러
매주 월요일 00시에 모든 크롤링을 실행하고 ChromaDB에 적재
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.logger.custom_logger import get_logger
from src.service.scheduler.crawling_job import run_crawling_job

logger = get_logger(__name__)


class CrawlingScheduler:
    """크롤링 스케줄러 클래스"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
        self._setup_jobs()
    
    def _setup_jobs(self):
        """스케줄 작업 설정"""
        # 매주 월요일 00:00에 크롤링 실행
        self.scheduler.add_job(
            run_crawling_job,
            trigger=CronTrigger(
                day_of_week='mon',  # 월요일
                hour=0,             # 0시
                minute=0,           # 0분
                timezone='Asia/Seoul'
            ),
            id='weekly_crawling',
            name='주간 크롤링 작업',
            replace_existing=True
        )
        
        logger.info("크롤링 스케줄 설정 완료: 매주 월요일 00:00")
    
    def start(self):
        """스케줄러 시작"""
        try:
            self.scheduler.start()
            logger.info("크롤링 스케줄러 시작됨")
            
            # 등록된 작업 목록 출력
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                logger.info(f"등록된 작업: {job.name} (다음 실행: {job.next_run_time})")
        
        except Exception as e:
            logger.error(f"스케줄러 시작 중 오류: {e}")
            raise
    
    def shutdown(self):
        """스케줄러 종료"""
        try:
            self.scheduler.shutdown()
            logger.info("크롤링 스케줄러 종료됨")
        except Exception as e:
            logger.error(f"스케줄러 종료 중 오류: {e}")
    
    async def run_now(self):
        """즉시 크롤링 실행 (테스트용)"""
        logger.info("수동 크롤링 실행 요청")
        await run_crawling_job()


# 전역 스케줄러 인스턴스
scheduler = CrawlingScheduler()