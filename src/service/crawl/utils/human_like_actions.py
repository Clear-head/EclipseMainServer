"""
사람처럼 행동하는 유틸리티 (봇 감지 회피)
"""
import asyncio
import random

from playwright.async_api import Locator


class HumanLikeActions:
    """사람처럼 행동하는 액션 클래스"""
    
    @staticmethod
    async def human_like_click(element: Locator):
        """
        사람처럼 클릭 (호버 → 대기 → 클릭)
        
        Args:
            element: 클릭할 Playwright 요소
        """
        try:
            # 화면에 보이도록 스크롤
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.3, 0.7))
            
            # 마우스 호버
            await element.hover()
            await asyncio.sleep(random.uniform(0.2, 0.5))
            
            # 클릭 시도
            try:
                clickable = element.locator('div, li[role="button"]').first
                await clickable.click(timeout=5000)
            except:
                await element.click(timeout=5000)
                
        except Exception as e:
            # 강제 클릭
            try:
                await element.click(force=True, timeout=5000)
            except Exception as force_error:
                raise Exception(f"클릭 실패: {force_error}")
    
    @staticmethod
    async def random_delay(base_delay: int = 20):
        """
        랜덤 딜레이 (base_delay ± 20%)
        
        Args:
            base_delay: 기본 딜레이 (초)
        """
        delay = random.uniform(base_delay * 0.8, base_delay * 1.2)
        await asyncio.sleep(delay)
    
    @staticmethod
    async def long_break(interval: int = 10):
        """
        N개마다 긴 휴식
        
        Args:
            interval: 휴식 간격
        """
        rest_time = random.uniform(20, 40)
        await asyncio.sleep(rest_time)