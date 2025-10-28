import asyncio
import re
import os
import aiohttp
from typing import Optional, Tuple, List
from playwright.async_api import Page
from dotenv import load_dotenv

from src.logger.custom_logger import get_logger

logger = get_logger(__name__)

class StoreDetailExtractor:
    """상점 상세 정보 추출 클래스 (공통)"""
    
    def __init__(self, frame, page: Page):
        self.frame = frame
        self.page = page
        
        # GitHub Copilot API 설정
        self.api_token = os.getenv('COPILOT_API_KEY') or os.getenv('GITHUB_TOKEN')
        if self.api_token:
            self.api_endpoint = "https://api.githubcopilot.com/chat/completions"
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        else:
            logger.warning("GitHub API 토큰이 없습니다. 영업시간 정리 기능이 비활성화됩니다.")
    
    def _clean_utf8_string(self, text: str) -> str:
        """4바이트 UTF-8 문자 제거 (이모지 등)"""
        if not text:
            return text
        cleaned = text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
        cleaned = cleaned.replace('\n', ' ')
        return cleaned
    
    async def extract_all_details(self) -> Optional[Tuple]:
        """
        모든 상세 정보 추출
        
        Returns:
            Tuple: (name, full_address, phone, business_hours, image, sub_category, tag_reviews)
        """
        try:
            name = await self._extract_title()
            full_address = await self._extract_address()
            phone = await self._extract_phone()
            business_hours = await self._extract_business_hours()
            image = await self._extract_image()
            sub_category = await self._extract_sub_category()
            tag_reviews = await self._extract_tag_reviews()
            
            logger.info(f"상점 정보 추출 완료: {name}")
            
            return (name, full_address, phone, business_hours, image, sub_category, tag_reviews)
            
        except Exception as e:
            logger.error(f"상점 정보 추출 중 오류: {e}")
            return None
    
    async def _extract_title(self) -> str:
        """매장명 추출"""
        try:
            name_locator = self.frame.locator('span.GHAhO')
            return await name_locator.inner_text(timeout=5000)
        except:
            return ""
    
    def _is_postal_code(self, text: str) -> bool:
        """우편번호인지 확인 (숫자로만 구성되어 있는지)"""
        return bool(text and re.match(r'^\d+$', text.strip()))
    
    async def _extract_address(self) -> str:
        """주소 추출 (지번 주소)"""
        try:
            # 주소 버튼 클릭
            address_section = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D')
            await address_section.scroll_into_view_if_needed()
            await asyncio.sleep(1)
            
            address_button = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D > div > a')
            await address_button.wait_for(state='visible', timeout=5000)
            await asyncio.sleep(0.5)
            
            await address_button.click()
            await asyncio.sleep(2)
            
            # 지번 주소 추출 (먼저 nth-child(2) 시도)
            jibun_address_div = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D > div > div.Y31Sf > div:nth-child(2)')
            await jibun_address_div.wait_for(state='visible', timeout=5000)
            
            jibun_address = await jibun_address_div.evaluate('''
                (element) => {
                    let text = '';
                    for (let node of element.childNodes) {
                        if (node.nodeType === Node.TEXT_NODE) {
                            text += node.textContent;
                        }
                    }
                    return text.trim();
                }
            ''')
            
            # 우편번호인지 확인
            if self._is_postal_code(jibun_address):
                logger.info(f"우편번호 감지됨: {jibun_address}, nth-child(1)로 재시도")
                
                # nth-child(1)로 재시도
                jibun_address_div_alt = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D > div > div.Y31Sf > div:nth-child(1)')
                await jibun_address_div_alt.wait_for(state='visible', timeout=5000)
                
                jibun_address = await jibun_address_div_alt.evaluate('''
                    (element) => {
                        let text = '';
                        for (let node of element.childNodes) {
                            if (node.nodeType === Node.TEXT_NODE) {
                                text += node.textContent;
                            }
                        }
                        return text.trim();
                    }
                ''')
            
            # 버튼 닫기
            try:
                await address_button.click()
                await asyncio.sleep(0.5)
            except:
                pass
            
            return jibun_address
        except:
            # 기본 주소 시도
            try:
                fallback_locator = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D > div > a > span.LDgIH')
                return await fallback_locator.inner_text(timeout=3000)
            except:
                return ""
    
    async def _extract_phone(self) -> str:
        """전화번호 추출 (클립보드 복사 방식 포함)"""
        try:
            # 1차 시도: 기본 전화번호 추출
            phone_locator = self.frame.locator('div.O8qbU.nbXkr > div > span.xlx7Q')
            phone = await phone_locator.inner_text(timeout=5000)
            if phone and phone.strip():
                return phone
        except Exception:
            pass
        
        # 2차 시도: 클립보드 복사 (개선된 버전)
        try:
            bf_button = self.frame.locator('a.BfF3H')
            
            if await bf_button.count() > 0:
                # 충분히 대기 후 강제 클릭
                await asyncio.sleep(1.5)
                
                try:
                    # force 클릭 시도
                    await bf_button.first.click(force=True, timeout=5000)
                except:
                    # JavaScript 클릭 시도
                    try:
                        await bf_button.first.evaluate('element => element.click()')
                    except:
                        logger.warning("BfF3H 버튼 클릭 실패, 대체 전화번호 건너뜀")
                        return ""
                
                await asyncio.sleep(1.5)
                
                # 복사 버튼 클릭
                bluelink_button = self.frame.locator('a.place_bluelink')
                
                if await bluelink_button.count() > 0:
                    try:
                        # force 클릭 시도
                        await bluelink_button.first.click(force=True, timeout=5000)
                    except:
                        # JavaScript 클릭 시도
                        try:
                            await bluelink_button.first.evaluate('element => element.click()')
                        except:
                            logger.warning("복사 버튼 클릭 실패")
                            return ""
                    
                    await asyncio.sleep(1)
                    
                    try:
                        clipboard_text = await self.page.evaluate('navigator.clipboard.readText()')
                        
                        if clipboard_text and clipboard_text.strip():
                            return clipboard_text.strip()
                    except Exception as clipboard_error:
                        logger.error(f"클립보드 읽기 실패: {clipboard_error}")
        except Exception as e:
            logger.error(f"대체 전화번호 추출 중 오류: {e}")
        
        return ""
    
    async def _extract_sub_category(self) -> str:
        """서브 카테고리 추출"""
        try:
            sub_category_locator = self.frame.locator('#_title > div > span.lnJFt')
            return await sub_category_locator.inner_text(timeout=5000)
        except:
            return ""
    
    async def _extract_business_hours(self) -> str:
        """영업시간 추출 및 LLM으로 정리"""
        try:
            business_hours_button = self.frame.locator('div.O8qbU.pSavy a').first
            
            if await business_hours_button.is_visible(timeout=5000):
                await business_hours_button.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                
                await business_hours_button.click()
                await asyncio.sleep(1)
                
                business_hours_locators = self.frame.locator('div.O8qbU.pSavy div.w9QyJ')
                hours_list = await business_hours_locators.all_inner_texts()
                
                if hours_list:
                    raw_hours = "\n".join(hours_list)
                    cleaned_hours = await self._clean_business_hours_with_llm(raw_hours)
                    return cleaned_hours
            return ""
        except:
            return ""
    
    async def _clean_business_hours_with_llm(self, raw_hours: str, max_retries: int = 10) -> str:
        """LLM을 사용하여 영업시간 정리 (비동기)"""
        if not self.api_token or not raw_hours:
            return raw_hours
        
        prompt = f"""다음은 상점의 영업시간 정보입니다. 중복되는 내용을 제거하고 간결하게 요약해주세요.

<원본 영업시간>
{raw_hours}

<지침>
1. 중복되는 정보는 하나로 통합하세요
2. 요일별 영업시간을 명확하게 정리하세요
3. 브레이크타임, 라스트오더 등 중요한 정보는 유지하세요
4. 불필요한 반복은 제거하세요
5. 간결하고 읽기 쉽게 정리하세요
6. 다른 설명 없이 정리된 영업시간만 답변하세요

답변 (정리된 영업시간만):"""
        
        payload = {
            "model": "gpt-4.1",
            "messages": [
                {"role": "system", "content": "당신은 상점 영업시간 정보를 간결하게 정리하는 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        self.api_endpoint,
                        headers=self.headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result['choices'][0]['message']['content'].strip()
                        else:
                            if attempt < max_retries:
                                await asyncio.sleep(1)
                            else:
                                return raw_hours
            except:
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    return raw_hours
        
        return raw_hours
    
    async def _extract_image(self) -> str:
        """이미지 URL 추출"""
        try:
            first_selector = 'div[role="main"] > div > div > a > img'
            first_image = self.frame.locator(first_selector).first
            
            if await first_image.count() > 0:
                src = await first_image.get_attribute('src', timeout=5000)
                if src:
                    return src
            
            second_selector = 'div[role="main"] > div > div > div > div > a > img'
            second_image = self.frame.locator(second_selector).first
            
            if await second_image.count() > 0:
                src = await second_image.get_attribute('src', timeout=5000)
                if src:
                    return src
            
            return ""
        except:
            return ""
    
    async def _extract_tag_reviews(self) -> List[Tuple[str, int]]:
        """태그 리뷰 추출"""
        tag_reviews = []
        
        try:
            # 리뷰 탭 클릭
            await self.frame.locator('a[href*="review"][role="tab"]').click()
            await asyncio.sleep(2)
            
            # 태그 리뷰 더보기 버튼 클릭
            while True:
                try:
                    show_more_button = self.frame.locator('div.mrSZf > div > a')
                    await show_more_button.click(timeout=3000)
                    await asyncio.sleep(1)
                except:
                    break
            
            # 태그 리뷰 추출
            opinion_elements = await self.frame.locator('div.mrSZf > ul > li').all()
            
            for opinion_element in opinion_elements:
                try:
                    review_tag = await opinion_element.locator('span.t3JSf').inner_text(timeout=3000)
                    rating = await opinion_element.locator('span.CUoLy').inner_text(timeout=3000)
                    cleaned_rating = int(re.sub(r'이 키워드를 선택한 인원\n', '', rating).replace(',', ''))
                    tag_reviews.append((review_tag, cleaned_rating))
                except:
                    continue
            
        except Exception as e:
            logger.error(f"태그 리뷰 추출 중 오류: {e}")
        
        return tag_reviews