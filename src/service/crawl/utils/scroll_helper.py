"""
스크롤 유틸리티 모듈 (용도별 분리)
"""
import asyncio
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


class FavoriteListScroller:
    """즐겨찾기 리스트 스크롤러 (iframe 내부)"""
    
    # 즐겨찾기 전용 컨테이너
    CONTAINER_SELECTORS = [
        '#app > div > div:nth-child(3)',
        '#app > div > div:nth-child(3) > div',
        'div[class*="scroll"]',
        'div[style*="overflow"]',
    ]
    
    @classmethod
    async def scroll_to_load_all(
        cls,
        frame_locator,
        item_selector: str,
        max_attempts: int = 500,
        delay: float = 2.0
    ) -> int:
        """
        즐겨찾기 목록을 끝까지 스크롤하여 모든 장소 로드
        
        Args:
            frame_locator: myPlaceBookmarkListIframe locator
            item_selector: 장소 선택자 (예: 'ul > li')
            max_attempts: 최대 스크롤 시도 횟수
            delay: 스크롤 간 대기 시간
            
        Returns:
            int: 로드된 장소 개수
        """
        logger.debug("📜 즐겨찾기 전체 스크롤 시작...")
        
        prev_count = 0
        same_count = 0
        max_same_count = 3
        
        for scroll_attempt in range(max_attempts):
            try:
                # 현재 장소 개수
                items = await frame_locator.locator(item_selector).all()
                current_count = len(items)
                
                # 로깅 (10회마다)
                if scroll_attempt % 10 == 0 and scroll_attempt > 0:
                    logger.debug(f"  스크롤 {scroll_attempt}회: {current_count}개 장소")
                
                # 개수 변화 체크
                if current_count == prev_count:
                    same_count += 1
                    if same_count >= max_same_count:
                        logger.debug(f"✅ 스크롤 완료: 총 {current_count}개")
                        break
                else:
                    same_count = 0
                
                prev_count = current_count
                
                # 마지막 요소로 스크롤
                if current_count > 0:
                    last_item = frame_locator.locator(item_selector).nth(current_count - 1)
                    try:
                        await last_item.scroll_into_view_if_needed(timeout=3000)
                    except:
                        pass
                
                # 컨테이너 스크롤
                for container_selector in cls.CONTAINER_SELECTORS:
                    try:
                        await frame_locator.locator(container_selector).evaluate(
                            'element => element.scrollTop = element.scrollHeight'
                        )
                        break
                    except:
                        continue
                
                await asyncio.sleep(delay)
                
            except Exception as e:
                logger.warning(f"스크롤 중 오류: {e}")
                break
        
        return prev_count
    
    @classmethod
    async def scroll_to_index(
        cls,
        frame_locator,
        item_selector: str,
        target_index: int
    ):
        """
        특정 인덱스까지만 스크롤
        
        Args:
            frame_locator: iframe locator
            item_selector: 장소 선택자
            target_index: 목표 인덱스 (0부터 시작)
        """
        logger.info(f"📜 {target_index+1}번째 항목까지 스크롤 중...")
        
        prev_count = 0
        same_count = 0
        
        for scroll_attempt in range(500):
            try:
                items = await frame_locator.locator(item_selector).all()
                current_count = len(items)
                
                # 목표 도달
                if current_count > target_index:
                    logger.debug(f"✅ 목표 도달: {current_count}개 로드")
                    break
                
                # 정체 체크
                if current_count == prev_count:
                    same_count += 1
                    if same_count >= 3:
                        logger.warning(f"⚠️ 스크롤 정체: {current_count}개")
                        break
                else:
                    same_count = 0
                
                prev_count = current_count
                
                # 마지막 요소 스크롤
                if current_count > 0:
                    last_item = frame_locator.locator(item_selector).nth(current_count - 1)
                    try:
                        await last_item.scroll_into_view_if_needed(timeout=3000)
                    except:
                        pass
                
                # 컨테이너 스크롤
                for container_selector in cls.CONTAINER_SELECTORS:
                    try:
                        await frame_locator.locator(container_selector).evaluate(
                            'element => element.scrollTop = element.scrollHeight'
                        )
                        break
                    except:
                        continue
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.warning(f"스크롤 중 오류: {e}")
                break


class SearchResultScroller:
    """검색 결과 스크롤러 (searchIframe 내부)"""
    
    # 검색 결과 전용 컨테이너
    CONTAINER_SELECTOR = '#_pcmap_list_scroll_container'
    ITEM_SELECTOR = '#_pcmap_list_scroll_container > ul > li'
    
    @classmethod
    async def scroll_current_page(
        cls,
        search_frame_locator,
        search_frame,
        scroll_step: int = 500,
        delay: float = 0.5
    ) -> int:
        """
        검색 결과 현재 페이지를 조금씩 천천히 스크롤
        (다음 페이지 버튼으로 이동하므로 전체 스크롤 불필요)
        
        Args:
            search_frame_locator: searchIframe locator
            search_frame: searchIframe frame
            scroll_step: 스크롤 단계 (px)
            delay: 스크롤 간 대기 시간
            
        Returns:
            int: 현재 페이지의 아이템 개수
        """
        try:
            # 스크롤 컨테이너 대기
            await search_frame_locator.locator(cls.CONTAINER_SELECTOR).wait_for(
                state='visible', timeout=5000
            )
            
            prev_count = 0
            same_count = 0
            max_same_count = 10
            
            for scroll_attempt in range(200):
                # 현재 아이템 개수
                items = await search_frame_locator.locator(cls.ITEM_SELECTOR).all()
                current_count = len(items)
                
                # 정체 체크
                if current_count == prev_count:
                    same_count += 1
                    if same_count >= max_same_count:
                        logger.debug(f"✅ 페이지 스크롤 완료: {current_count}개")
                        break
                else:
                    same_count = 0
                
                prev_count = current_count
                
                # 부드럽게 스크롤
                try:
                    await search_frame.evaluate(f'''
                        () => {{
                            const container = document.querySelector('{cls.CONTAINER_SELECTOR}');
                            if (container) {{
                                container.scrollBy({{
                                    top: {scroll_step},
                                    behavior: 'smooth'
                                }});
                            }}
                        }}
                    ''')
                except:
                    pass
                
                await asyncio.sleep(delay)
            
            return prev_count
            
        except Exception as e:
            logger.warning(f"검색 결과 스크롤 중 오류: {e}")
            return 0
    
    @classmethod
    async def reset_scroll_position(cls, search_frame):
        """
        스크롤을 맨 위로 초기화 (다음 페이지 이동 시)
        
        Args:
            search_frame: searchIframe frame
        """
        try:
            await search_frame.evaluate(f'''
                () => {{
                    const container = document.querySelector('{cls.CONTAINER_SELECTOR}');
                    if (container) {{
                        container.scrollTop = 0;
                    }}
                }}
            ''')
            await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"스크롤 초기화 실패 (무시): {e}")


class PageNavigator:
    """페이지네이션 네비게이터 (다음 페이지 이동)"""
    
    @staticmethod
    async def go_to_next_page_naver(search_frame_locator, search_frame) -> bool:
        """
        네이버 지도 검색 결과 다음 페이지 이동
        
        Args:
            search_frame_locator: searchIframe locator
            search_frame: searchIframe frame
            
        Returns:
            bool: 다음 페이지가 있으면 True
        """
        try:
            next_button_selector = 'a.eUTV2'
            next_buttons = await search_frame_locator.locator(next_button_selector).all()
            
            if len(next_buttons) == 0:
                return False
            
            # "다음페이지" 텍스트 찾기
            for button in next_buttons:
                try:
                    span_text = await button.locator('span').inner_text(timeout=1000)
                    
                    if span_text and '다음페이지' in span_text:
                        # disabled 체크
                        is_disabled = await button.get_attribute('aria-disabled')
                        
                        if is_disabled == 'true':
                            return False
                        
                        # 클릭
                        await button.click()
                        await asyncio.sleep(2)
                        
                        # 스크롤 초기화
                        await SearchResultScroller.reset_scroll_position(search_frame)
                        
                        logger.debug("✅ 다음 페이지로 이동")
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.warning(f"다음 페이지 이동 중 오류: {e}")
            return False
    
    @staticmethod
    async def go_to_next_page_bluer(page) -> bool:
        """
        Bluer 웹사이트 다음 페이지 이동
        
        Args:
            page: Playwright Page 객체
            
        Returns:
            bool: 다음 페이지가 있으면 True
        """
        try:
            await page.wait_for_selector('#page-selection > ul', timeout=5000)
            await asyncio.sleep(1)
            
            page_items = await page.locator('#page-selection > ul > li').all()
            
            # active 페이지 찾기
            active_index = -1
            for idx, item in enumerate(page_items):
                class_attr = await item.get_attribute('class')
                if class_attr and 'active' in class_attr:
                    active_index = idx
                    break
            
            if active_index == -1:
                return False
            
            # 다음 페이지 클릭
            next_index = active_index + 1
            if next_index >= len(page_items):
                return False
            
            next_button = page_items[next_index]
            await next_button.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            
            clickable = next_button.locator('a, button').first
            if await clickable.count() > 0:
                await clickable.click()
            else:
                await next_button.click()
            
            await asyncio.sleep(2)
            return True
            
        except Exception as e:
            logger.error(f"Bluer 다음 페이지 이동 중 오류: {e}")
            return False