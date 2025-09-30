import json
import asyncio
from playwright.async_api import async_playwright, TimeoutError, Page
import re
from typing import Optional
import sys, os
import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
# 새로 만든 스크래퍼 클래스를 임포트합니다.
from crawling_blog import NaverBlogReviewScraper
from models.default_review import StoreInfo
from models.blog_review import BlogReview
from logger.logger_handler import get_logger

# 로거 초기화
logger = get_logger('crawling_naver')

class NaverMapSingleCrawler:
    """네이버 지도 단일 매장 크롤링을 위한 클래스"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.naver_map_url = "https://map.naver.com/v5/search"
        
    async def crawl(self, search_keyword: str, output_file: str = 'results.json'):
        """메인 크롤링 함수 - 단일 매장"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            
            try:
                # 네이버 지도 접속 및 검색
                await self._navigate_to_naver_map(page)
                await self._search_keyword(page, search_keyword)
                
                # entryIframe이 바로 뜨는지 확인
                entry_frame = await self._get_entry_frame(page)
                if not entry_frame:
                    logger.error(f"'{search_keyword}' 매장 정보를 찾을 수 없습니다.")
                    return False
                
                # 크롤링 시작 로그
                logger.info(f"'{search_keyword}' 크롤링 시작")
                
                # 상세 정보 추출
                place_info = await self._extract_store_details(entry_frame, search_keyword, page)
                if place_info:
                    # 저장
                    self._save_single_store(output_file, place_info)
                    
                    # 크롤링 완료 로그
                    logger.info(f"'{place_info.title}' 크롤링 완료 및 저장됨")
                    return True
                else:
                    logger.error(f"'{search_keyword}' 매장 정보 추출 실패")
                    return False
                    
            except Exception as e:
                logger.error(f"'{search_keyword}' 크롤링 중 오류: {e}")
                return False
            finally:
                await browser.close()
    
    async def crawl_multiple(self, search_keywords: list, output_file: str = 'results.json', delay: int = 20):
        """여러 매장 순차 크롤링"""
        total = len(search_keywords)
        success_count = 0
        
        # logger.info(f"총 {total}개 매장 크롤링 시작")
        
        for idx, keyword in enumerate(search_keywords, 1):
            logger.info(f"[{idx}/{total}] '{keyword}' 크롤링 진행 중...")
            
            # 개별 매장 크롤링
            result = await self.crawl(keyword, output_file)
            
            if result:
                success_count += 1
            
            # 마지막 매장이 아니면 딜레이
            if idx < total:
                # logger.info(f"{delay}초 대기 중...")
                await asyncio.sleep(delay)
        
        logger.info(f"크롤링 완료: 성공 {success_count}/{total}")
        return success_count
    
    async def _navigate_to_naver_map(self, page):
        """네이버 지도 페이지로 이동"""
        await page.goto(self.naver_map_url)
    
    async def _search_keyword(self, page, keyword: str):
        """키워드 검색"""
        search_input_selector = '.input_search'
        await page.wait_for_selector(search_input_selector)
        await asyncio.sleep(1)
        
        # 검색창 초기화
        await page.fill(search_input_selector, '')
        await asyncio.sleep(0.5)
        
        await page.fill(search_input_selector, keyword)
        await page.press(search_input_selector, 'Enter')
    
    async def _get_entry_frame(self, page):
        """상세 정보 iframe 가져오기 - 바로 entryIframe 확인"""
        try:
            await page.wait_for_selector('iframe#entryIframe', timeout=10000)
            entry_frame = page.frame_locator('iframe#entryIframe')
            await asyncio.sleep(3)
            return entry_frame
        except TimeoutError:
            logger.error("entryIframe을 찾을 수 없습니다.")
            return None
    
    async def _extract_store_details(self, entry_frame, original_name: str, page: Page) -> Optional[StoreInfo]:
        """상점 상세 정보 추출 (블로그 리뷰 스크래핑 추가)"""
        extractor = StoreDetailExtractor(entry_frame, page)
        return await extractor.extract_all_details(original_name)
    
    def _load_existing_data(self, output_file: str) -> list:
        """기존 JSON 파일 데이터 로드"""
        try:
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data
        except Exception as e:
            logger.error(f"기존 데이터 로드 중 오류: {e}")
        
        return []
    
    def _create_store_key(self, title: str, address: str) -> str:
        """상점 식별을 위한 키 생성 (title + address 조합)"""
        title = title or 'Unknown'
        address = address or ''
        return f"{title}||{address}"
    
    def _save_single_store(self, output_file: str, new_store: StoreInfo):
        """단일 상점 정보를 파일에 추가/업데이트"""
        # 기존 데이터 로드
        existing_data = self._load_existing_data(output_file)
        
        # 딕셔너리로 변환
        existing_dict = {}
        for item in existing_data:
            key = self._create_store_key(item.get('title', ''), item.get('address', ''))
            existing_dict[key] = item
        
        # 새 데이터 추가/업데이트
        new_item = self._convert_empty_to_null(new_store.model_dump())
        key = self._create_store_key(new_item.get('title') or '', new_item.get('address') or '')
        existing_dict[key] = new_item
        
        # 전체 데이터 저장
        all_data = list(existing_dict.values())
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4, default=str)
        
        # logger.info(f"'{new_item.get('title', 'Unknown')}' 데이터 저장 완료 (총 {len(all_data)}개)")
    
    def _convert_empty_to_null(self, data):
        """빈 값을 null로 변환하는 헬퍼 함수"""
        if isinstance(data, dict):
            return {key: self._convert_empty_to_null(value) for key, value in data.items()}
        elif isinstance(data, list):
            if len(data) == 0:
                return None
            return [self._convert_empty_to_null(item) for item in data]
        elif isinstance(data, str):
            return None if data == "" else data
        else:
            return data


class StoreDetailExtractor:
    """상점 상세 정보 추출을 위한 클래스"""
    
    def __init__(self, frame, page: Page):
        self.frame = frame
        self.page = page
    
    async def extract_all_details(self, original_name: str) -> Optional[StoreInfo]:
        """모든 상세 정보 추출"""
        
        try:
            # 기본 정보 추출
            title = await self._extract_title(original_name)
            address = await self._extract_address()
            phone = await self._extract_phone()
            business_hours = await self._extract_business_hours()
            image = await self._extract_image()
            
            # 리뷰 정보 추출
            opinion_data, content_data = await self._extract_reviews()
            
            # 블로그 리뷰 스크래퍼 호출
            scraper = NaverBlogReviewScraper(self.page, self.frame)
            blog_reviews = await scraper.scrape_blog_reviews()
            
            # StoreInfo 모델로 데이터 통합
            return StoreInfo(
                title=title or "",
                address=address or "",
                phone=phone or "",
                business_hours=business_hours or "",
                image=image or "",
                opinion=opinion_data or [],
                content=content_data or [],
                blog_review=blog_reviews or [],
                last_crawl=datetime.datetime.now()
            )
            
        except Exception as e:
            logger.error(f"상점 정보 추출 중 오류: {e}")
            return None
    
    async def _extract_title(self, original_name: str) -> str:
        """매장명 추출"""
        try:
            name_locator = self.frame.locator('span.GHAhO')
            return await name_locator.inner_text(timeout=5000)
        except TimeoutError:
            logger.error(f"매장명 추출 Timeout")
            return original_name
        except Exception as e:
            logger.error(f"매장명 추출 오류: {e}")
            return original_name
    
    async def _extract_address(self) -> Optional[str]:
        """주소 추출"""
        try:
            address_locator = self.frame.locator('#app-root > div > div > div:nth-child(6) > div > div:nth-child(2) > div.place_section_content > div > div.O8qbU.tQY7D > div > a > span.LDgIH')
            return await address_locator.inner_text(timeout=5000)
        except TimeoutError:
            logger.error(f"주소 추출 Timeout")
            return ""
        except Exception as e:
            logger.error(f"주소 추출 오류: {e}")
            return ""
    
    async def _extract_phone(self) -> Optional[str]:
        """전화번호 추출"""
        try:
            phone_locator = self.frame.locator('div.O8qbU.nbXkr > div > span.xlx7Q')
            return await phone_locator.inner_text(timeout=5000)
        except TimeoutError:
            logger.error(f"전화번호 추출 Timeout")
            return ""
        except Exception as e:
            logger.error(f"전화번호 추출 오류: {e}")
            return ""
    
    async def _extract_business_hours(self) -> str:
        """영업시간 추출"""
        try:
            business_hours_button = self.frame.locator('div.O8qbU.pSavy a').first
            
            if await business_hours_button.is_visible(timeout=5000):
                await business_hours_button.click()
                await asyncio.sleep(1)
                
                business_hours_locators = self.frame.locator('div.O8qbU.pSavy div.w9QyJ')
                hours_list = await business_hours_locators.all_inner_texts()
                return ", ".join(hours_list) if hours_list else ""
            else:
                logger.error(f"영업시간 추출 실패")
                return ""
        except Exception as e:
            logger.error(f"영업시간 추출 오류: {e}")
            return ""
    
    async def _extract_image(self) -> Optional[str]:
        """이미지 URL 추출"""
        try:
            # 첫 번째 선택자 시도: div[role="main"] > div > div > a > img
            first_selector = 'div[role="main"] > div > div > a > img'
            first_image = self.frame.locator(first_selector).first
            
            if await first_image.count() > 0:
                src = await first_image.get_attribute('src', timeout=5000)
                if src:
                    return src
            
            # 두 번째 선택자 시도: div[role="main"] > div > div > div > div > a > img
            second_selector = 'div[role="main"] > div > div > div > div > a > img'
            second_image = self.frame.locator(second_selector).first
            
            if await second_image.count() > 0:
                src = await second_image.get_attribute('src', timeout=5000)
                if src:
                    return src
            
            return ""
            
        except TimeoutError:
            logger.error(f"이미지 추출 Timeout")
            return ""
        except Exception as e:
            logger.error(f"이미지 추출 중 오류: {e}")
            return ""
    
    async def _extract_reviews(self):
        """리뷰 정보 추출"""
        opinion_data = []
        content_data = []
        
        try:
            # 리뷰 탭 클릭
            await self.frame.locator('a[href*="review"][role="tab"]').click()
            await asyncio.sleep(2)
            
            # 리뷰 더보기 버튼 클릭
            await self._click_review_show_more_buttons()
            
            # 리뷰 태그 추출
            opinion_data = await self._extract_review_tags()
            
            # 상세 리뷰 추출
            content_data = await self._extract_detailed_reviews()
            
        except Exception as e:
            logger.error(f"리뷰 탭 클릭 또는 추출 중 오류: {e}")
        
        return opinion_data, content_data
    
    async def _click_review_show_more_buttons(self):
        """리뷰 더보기 버튼들 클릭"""
        # 첫 번째 더보기 버튼
        while True:
            try:
                show_more_button = self.frame.locator('div.mrSZf > div > a')
                await show_more_button.click(timeout=3000)
                await asyncio.sleep(1)
            except TimeoutError:
                break
        
        # 두 번째 더보기 버튼
        while True:
            try:
                show_more_button = self.frame.locator('div.NSTUp > div > a')
                await show_more_button.click(timeout=3000)
                await asyncio.sleep(1)
            except TimeoutError:
                break
    
    async def _extract_review_tags(self) -> list:
        """리뷰 태그 추출"""
        opinion_data = []
        try:
            opinion_elements = await self.frame.locator('div.mrSZf > ul > li').all()
            
            for opinion_element in opinion_elements:
                try:
                    review_tag = await opinion_element.locator('span.t3JSf').inner_text(timeout=3000)
                    rating = await opinion_element.locator('span.CUoLy').inner_text(timeout=3000)
                    cleaned_rating = int(re.sub(r'이 키워드를 선택한 인원\n', '', rating).replace(',', ''))
                    opinion_data.append((review_tag, cleaned_rating))
                except (TimeoutError, ValueError) as e:
                    logger.error(f"리뷰 태그 또는 평점 추출 중 오류: {e}")
                    continue
        except Exception as e:
            logger.error(f"리뷰 태그 전체 추출 중 오류: {e}")
        
        return opinion_data
    
    async def _extract_detailed_reviews(self) -> list:
        """상세 리뷰 추출"""
        content_data = []
        try:
            review_elements = await self.frame.locator('ul#_review_list > li').all()
            
            for review_element in review_elements:
                try:
                    # 더보기 버튼 클릭
                    more_button_locator = review_element.locator('div.pui__vn15t2 > a').first
                    
                    if await more_button_locator.is_visible():
                        await more_button_locator.click(timeout=3000)
                        await asyncio.sleep(1)
                    
                    # 리뷰 텍스트 추출
                    review_text_list = await review_element.locator('div.pui__vn15t2 > a').all_inner_texts()
                    full_review_text = " ".join(review_text_list)
                    if full_review_text.strip():
                        content_data.append(full_review_text)
                    
                except TimeoutError:
                    logger.error(f"개별 리뷰 추출 중 Timeout")
                    continue
                except Exception as e:
                    logger.error(f"개별 리뷰 추출 중 오류: {e}")
                    continue
        except Exception as e:
            logger.error(f"상세 리뷰 전체 추출 중 오류: {e}")
        
        return content_data


async def main():
    """메인 함수"""
    # 검색할 매장 리스트
    search_keywords = [
        "꾸석지돌판한우 장승배기점",
        "서울 동작구 흑석로 배스킨라빈스 중앙대점"
    ]
    
    output_file = 'results.json'
    delay_seconds = 20  # 매장 간 딜레이 (초)
    
    crawler = NaverMapSingleCrawler(headless=False)
    await crawler.crawl_multiple(search_keywords, output_file, delay=delay_seconds)

if __name__ == "__main__":
    asyncio.run(main())