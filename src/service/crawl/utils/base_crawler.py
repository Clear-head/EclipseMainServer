"""
크롤링 베이스 클래스
"""
from abc import ABC, abstractmethod

from playwright.async_api import async_playwright, Page, Browser

from src.logger.custom_logger import get_logger
from src.service.crawl.utils.human_like_actions import HumanLikeActions
from src.service.crawl.utils.optimized_browser_manager import (
    OptimizedBrowserManager,
    BatchCrawlingMixin
)
from src.service.crawl.utils.scroll_helper import ScrollHelper
from src.service.crawl.utils.store_data_saver import StoreDataSaver

logger = get_logger(__name__)


class BaseCrawler(ABC, BatchCrawlingMixin):
    """모든 크롤러의 베이스 클래스"""
    
    RESTART_INTERVAL = 30  # 배치 크기 (오버라이드 가능)
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.logger = logger
        self.data_saver = StoreDataSaver()
        self.human_actions = HumanLikeActions()
        self.scroll_helper = ScrollHelper()
    
    async def crawl(self, **kwargs):
        """메인 크롤링 진입점"""
        async with async_playwright() as p:
            browser = await OptimizedBrowserManager.create_optimized_browser(p, self.headless)
            
            try:
                await self._execute_crawling(browser, **kwargs)
            except Exception as e:
                self.logger.error(f"크롤링 중 오류: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                await browser.close()
    
    @abstractmethod
    async def _execute_crawling(self, browser: Browser, **kwargs):
        """
        실제 크롤링 로직 (서브클래스에서 구현)
        
        Args:
            browser: 브라우저 인스턴스
            **kwargs: 추가 파라미터
        """
        pass
    
    @abstractmethod
    async def _crawl_single_item(self, page: Page, item):
        """
        단일 아이템 크롤링 (서브클래스에서 구현)
        
        Args:
            page: Playwright Page 객체
            item: 크롤링할 아이템
            
        Returns:
            크롤링 결과 또는 None
        """
        pass