"""
메모리 최적화 + 봇 우회 브라우저 관리 모듈
"""
from playwright.async_api import Browser, BrowserContext

from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


class OptimizedBrowserManager:
    """메모리 최적화 + 봇 탐지 회피 브라우저 매니저"""
    
    # 메모리 최적화 브라우저 args
    OPTIMIZED_ARGS = [
        '--enable-features=ClipboardAPI',
        '--disable-dev-shm-usage',  # 공유 메모리 사용 안 함 (OOM 방지)
        '--disable-gpu',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',  # 자동화 플래그 숨김
        '--window-size=1920,1080',
        '--max-old-space-size=4096',  # JavaScript 힙 메모리 4GB 제한
        '--disable-extensions',
        '--disable-background-networking',
        '--disable-background-timer-throttling',
        '--disable-renderer-backgrounding',
        '--disable-features=TranslateUI',
        '--mute-audio',
        '--no-first-run',
    ]
    
    # 봇 탐지 회피 스크립트
    STEALTH_SCRIPT = """
        // webdriver 플래그 숨기기
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Chrome 객체 추가
        window.chrome = {
            runtime: {}
        };
        
        // Permissions API 우회
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // plugins 추가
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        // languages 추가
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ko-KR', 'ko', 'en-US', 'en']
        });
    """
    
    @classmethod
    async def create_optimized_browser(cls, playwright, headless: bool = False) -> Browser:
        """
        메모리 최적화 브라우저 생성
        
        Args:
            playwright: Playwright 인스턴스
            headless: 헤드리스 모드 여부
            
        Returns:
            Browser: 최적화된 브라우저
        """
        return await playwright.chromium.launch(
            headless=headless,
            args=cls.OPTIMIZED_ARGS
        )
    
    @classmethod
    async def create_stealth_context(
        cls, 
        browser: Browser,
        permissions: list = None
    ) -> BrowserContext:
        """
        봇 탐지 회피 컨텍스트 생성
        
        Args:
            browser: 브라우저 인스턴스
            permissions: 권한 목록
            
        Returns:
            BrowserContext: 스텔스 컨텍스트
        """
        permissions = permissions or ['clipboard-read', 'clipboard-write']
        
        context = await browser.new_context(
            permissions=permissions,
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ko-KR',
            timezone_id='Asia/Seoul',
        )
        
        # 봇 탐지 회피 스크립트 주입
        await context.add_init_script(cls.STEALTH_SCRIPT)
        
        return context
    
    @staticmethod
    async def clear_page_resources(page):
        """
        페이지 리소스 정리 (메모리 최적화)
        
        Args:
            page: Playwright Page 객체
        """
        try:
            await page.evaluate("""
                () => {
                    // JavaScript 가비지 컬렉션
                    if (window.gc) {
                        window.gc();
                    }
                    
                    // 스크롤 초기화
                    window.scrollTo(0, 0);
                }
            """)
        except Exception as e:
            logger.debug(f"리소스 정리 중 오류 (무시): {e}")


class BatchCrawlingMixin:
    """배치 크롤링 믹스인 (공통 로직)"""
    
    RESTART_INTERVAL = 30  # 기본 배치 크기
    
    async def execute_batch_crawling(
        self,
        browser: Browser,
        items: list,
        crawl_func,
        delay: int = 20
    ):
        """
        배치 단위로 크롤링 실행
        
        Args:
            browser: 브라우저 인스턴스
            items: 크롤링할 아이템 목록
            crawl_func: 크롤링 함수 (page, batch, batch_start, total) -> None
            delay: 기본 딜레이
        """
        import asyncio
        import random
        
        total = len(items)
        
        for batch_start in range(0, total, self.RESTART_INTERVAL):
            batch_end = min(batch_start + self.RESTART_INTERVAL, total)
            batch = items[batch_start:batch_end]
            
            batch_num = batch_start // self.RESTART_INTERVAL + 1
            total_batches = (total + self.RESTART_INTERVAL - 1) // self.RESTART_INTERVAL
            
            logger.info(f"🔄 배치 {batch_num}/{total_batches}: {batch_start+1}~{batch_end}/{total}")
            
            # 새 컨텍스트 생성
            context = await OptimizedBrowserManager.create_stealth_context(browser)
            page = await context.new_page()
            
            try:
                # 배치 크롤링 실행
                await crawl_func(page, batch, batch_start, total)
                
            except Exception as e:
                logger.error(f"배치 {batch_num} 처리 중 오류: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                await context.close()
                await asyncio.sleep(3)
                
                # 배치 간 휴식
                if batch_end < total:
                    rest_time = random.uniform(30, 60)
                    logger.info(f"🛌 배치 {batch_num} 완료, {rest_time:.0f}초 휴식...\n")
                    await asyncio.sleep(rest_time)