import asyncio
from playwright.async_api import Page, FrameLocator, TimeoutError
import re
from typing import List, Tuple, Optional
from datetime import datetime
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# 로거 import 및 초기화
from logger.logger_handler import get_logger
from models.blog_review import BlogReview

# 로거 초기화
logger = get_logger('crawling_naver')

class NaverBlogReviewScraper:
    """
    네이버 지도 상세 페이지에서 블로그 리뷰를 긁어오는 클래스
    """
    def __init__(self, page: Page, entry_frame: FrameLocator):
        self.page = page
        self.entry_frame = entry_frame
        self.blog_tab_selector = '#_subtab_view > div > a:nth-child(2)'
        self.blog_list_selector = 'div.place_section_content ul > li'
        self.blog_iframe_selector = '#mainFrame'
        self.blog_content_selector = 'div.se_component_wrap'

    async def scrape_blog_reviews(self) -> List[BlogReview]:
        """
        상점의 블로그 리뷰를 긁어와 BlogReview 객체 리스트로 반환합니다.
        """
        blog_reviews = []
        
        if not await self._navigate_to_blog_tab():
            return []
        
        blog_list_items = await self._get_blog_list_items()
        if not blog_list_items:
            return []
        
        max_items = len(blog_list_items)
        
        for i in range(max_items):
            try:
                blog_review = await self._process_blog_item(blog_list_items[i], i, max_items)
                if blog_review:
                    blog_reviews.append(blog_review)
                
                # 다음 블로그 리뷰를 시작하기 전 대기
                if i < max_items - 1:
                    await self._wait_between_requests()
                    
            except Exception as e:
                logger.error(f"블로그 리뷰 항목 {i+1}번 처리 중 오류: {e}")
                continue

        return blog_reviews

    async def _navigate_to_blog_tab(self) -> bool:
        """
        블로그 리뷰 탭으로 이동합니다.
        
        Returns:
            bool: 성공 시 True, 실패 시 False
        """
        try:
            await self.entry_frame.locator(self.blog_tab_selector).click()
            await asyncio.sleep(2)
            return True
        except TimeoutError:
            logger.error("블로그 리뷰 탭을 찾을 수 없습니다.")
            return False
        except Exception as e:
            logger.error(f"블로그 리뷰 탭 이동 중 오류: {e}")
            return False

    async def _get_blog_list_items(self) -> List:
        """
        블로그 리스트 아이템들을 가져옵니다.
        
        Returns:
            List: 블로그 리스트 아이템들
        """
        try:
            blog_list_items = await self.entry_frame.locator(self.blog_list_selector).all()
            return blog_list_items
        except Exception as e:
            logger.error(f"블로그 리스트 아이템 가져오기 중 오류: {e}")
            return []

    async def _process_blog_item(self, item, index: int, total: int) -> Optional[BlogReview]:
        """
        개별 블로그 아이템을 처리합니다.
        
        Args:
            item: 블로그 리스트 아이템
            index: 현재 인덱스
            total: 전체 아이템 수
            
        Returns:
            Optional[BlogReview]: 성공 시 BlogReview 객체, 실패 시 None
        """
        blog_link_locator = item.locator('a').first
        if not await blog_link_locator.is_visible():
            return None
        
        # 새 페이지 열기
        blog_page = await self._open_blog_page(blog_link_locator)
        if not blog_page:
            return None
        
        try:
            # 콘텐츠와 날짜 추출
            review_content, created_at = await self._extract_content_and_date(blog_page)
            
            if review_content and review_content.strip():
                return BlogReview(content=review_content, create_at=created_at)
            
            return None
            
        finally:
            # 블로그 탭을 닫고 원래 페이지로 돌아가기
            await self._close_blog_page_and_return(blog_page)

    async def _open_blog_page(self, blog_link_locator) -> Optional[Page]:
        """
        블로그 링크를 클릭하여 새 페이지를 엽니다.
        
        Args:
            blog_link_locator: 블로그 링크 locator
            
        Returns:
            Optional[Page]: 성공 시 새 페이지 객체, 실패 시 None
        """
        try:
            async with self.page.context.expect_page() as new_page_event:
                await blog_link_locator.click()
                
            blog_page = await new_page_event.value
            await blog_page.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(2)
            
            return blog_page
        except Exception as e:
            logger.error(f"새 페이지 열기 중 오류: {e}")
            return None

    async def _close_blog_page_and_return(self, blog_page: Page):
        """
        블로그 페이지를 닫고 원래 페이지로 돌아갑니다.
        
        Args:
            blog_page: 닫을 블로그 페이지
        """
        try:
            await blog_page.close()
            await self.page.bring_to_front()
        except Exception as e:
            logger.error(f"페이지 닫기 중 오류: {e}")

    async def _wait_between_requests(self):
        """
        요청 사이의 대기 시간을 처리합니다.
        """
        await asyncio.sleep(20)

    async def _extract_content_and_date(self, blog_page: Page) -> Tuple[str, datetime]:
        """
        블로그 페이지에서 게시글 본문 내용과 작성일자를 추출합니다.
        
        Args:
            blog_page: 블로그 페이지 객체
            
        Returns:
            Tuple[str, datetime]: (콘텐츠, 작성일자)
        """
        content_frame = self._get_content_frame(blog_page)
        content_text = await self._extract_blog_content(blog_page, content_frame)
        created_at = await self._extract_creation_date(blog_page, content_frame)
        
        return content_text, created_at

    def _get_content_frame(self, blog_page: Page):
        """
        콘텐츠 프레임을 가져옵니다.
        
        Args:
            blog_page: 블로그 페이지 객체
            
        Returns:
            프레임 객체 또는 페이지 객체
        """
        try:
            return blog_page.frame_locator(self.blog_iframe_selector)
        except Exception as e:
            logger.error(f"프레임 선택 중 오류: {e}")
            return blog_page

    async def _extract_blog_content(self, blog_page: Page, content_frame) -> str:
        """
        블로그 콘텐츠를 추출합니다.
        
        Args:
            blog_page: 블로그 페이지 객체
            content_frame: 콘텐츠 프레임
            
        Returns:
            str: 추출된 콘텐츠
        """
        content_text = ""
        
        # 동적 선택자로 시도
        content_text = await self._try_dynamic_selector(blog_page, content_frame)
        
        # 동적 선택자가 실패했을 경우, 일반 선택자로 재시도
        if not content_text or len(content_text.strip()) < 50:
            content_text = await self._try_general_selectors(content_frame)
        
        return content_text

    async def _try_dynamic_selector(self, blog_page: Page, content_frame) -> str:
        """
        URL에서 글번호를 추출하여 동적 선택자로 콘텐츠를 추출합니다.
        
        Args:
            blog_page: 블로그 페이지 객체
            content_frame: 콘텐츠 프레임
            
        Returns:
            str: 추출된 콘텐츠
        """
        try:
            url_match = re.search(r'blog\.naver\.com/([^/]+)/(\d+)', blog_page.url)
            if not url_match:
                return ""
            
            post_number = url_match.group(2)
            dynamic_selector = f'#post-view{post_number} .se-main-container'
            
            await content_frame.locator(dynamic_selector).wait_for(timeout=10000)
            content_elements = await content_frame.locator(dynamic_selector).all()
            
            content_text = ""
            for element in content_elements:
                text = await element.inner_text()
                if text and text.strip():
                    content_text += text + "\n"
            
            return content_text
            
        except TimeoutError:
            return ""
        except Exception as e:
            logger.error(f"동적 선택자 처리 중 오류: {e}")
            return ""

    async def _try_general_selectors(self, content_frame) -> str:
        """
        일반 선택자들을 사용하여 콘텐츠를 추출합니다.
        
        Args:
            content_frame: 콘텐츠 프레임
            
        Returns:
            str: 추출된 콘텐츠
        """
        try:
            # 기본 선택자 시도
            content_element = content_frame.locator(self.blog_content_selector).first
            await content_element.wait_for(timeout=10000)
            content_text = await content_element.inner_text()
            
            if content_text and len(content_text.strip()) > 50:
                return content_text
            
            # 다른 선택자들 시도
            return await self._try_alternative_selectors(content_frame)
            
        except TimeoutError:
            return ""
        except Exception as e:
            logger.error(f"콘텐츠 추출 중 오류: {e}")
            return ""

    async def _try_alternative_selectors(self, content_frame) -> str:
        """
        대안 선택자들을 시도하여 콘텐츠를 추출합니다.
        
        Args:
            content_frame: 콘텐츠 프레임
            
        Returns:
            str: 추출된 콘텐츠
        """
        selectors_to_try = [
            '.se-main-container',
            '.post-view',
            '#postListBody',
            '.post_ct'
        ]
        
        for selector in selectors_to_try:
            try:
                element = content_frame.locator(selector).first
                if await element.count() > 0:
                    content_text = await element.inner_text(timeout=5000)
                    if content_text and len(content_text.strip()) > 50:
                        return content_text
            except:
                continue
        
        return ""

    async def _extract_creation_date(self, blog_page: Page, content_frame) -> datetime:
        """
        블로그 게시글의 작성일자를 추출합니다.
        
        Args:
            blog_page: 블로그 페이지 객체
            content_frame: 콘텐츠 프레임
            
        Returns:
            datetime: 작성일자 (추출 실패 시 현재 시간)
        """
        try:
            date_selectors = [
                'span.se_publishDate',
                '.post_date',
                '.date',
                '.blog_date'
            ]
            
            created_at_str = await self._find_date_text(blog_page, content_frame, date_selectors)
            
            if created_at_str:
                return self._parse_date_string(created_at_str)
            
            return datetime.now()
            
        except Exception as e:
            logger.error(f"작성일자 추출 중 오류: {e}")
            return datetime.now()

    async def _find_date_text(self, blog_page: Page, content_frame, date_selectors: List[str]) -> Optional[str]:
        """
        날짜 선택자들을 사용하여 날짜 텍스트를 찾습니다.
        
        Args:
            blog_page: 블로그 페이지 객체
            content_frame: 콘텐츠 프레임
            date_selectors: 날짜 선택자 목록
            
        Returns:
            Optional[str]: 찾은 날짜 텍스트 또는 None
        """
        for date_selector in date_selectors:
            try:
                if content_frame == blog_page:  # iframe이 아닌 경우
                    created_at_str = await blog_page.locator(date_selector).first.inner_text(timeout=3000)
                else:
                    created_at_str = await content_frame.locator(date_selector).first.inner_text(timeout=3000)
                
                if created_at_str:
                    return created_at_str
            except:
                continue
        
        return None

    def _parse_date_string(self, date_str: str) -> datetime:
        """
        날짜 문자열을 datetime 객체로 변환합니다.
        
        Args:
            date_str: 날짜 문자열
            
        Returns:
            datetime: 변환된 datetime 객체 (실패 시 현재 시간)
        """
        date_formats = [
            '%Y. %m. %d. %H:%M',
            '%Y. %m. %d.',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%Y.%m.%d',
            '%m.%d'
        ]
        
        for date_format in date_formats:
            try:
                return datetime.strptime(date_str.strip(), date_format)
            except ValueError:
                continue
        
        logger.error(f"알 수 없는 날짜 형식: {date_str}")
        return datetime.now()