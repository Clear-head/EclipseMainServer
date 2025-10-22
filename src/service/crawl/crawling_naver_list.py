import json
import asyncio
from playwright.async_api import async_playwright, TimeoutError, Page
import re
from typing import Optional, List, Tuple
import sys, os
import datetime
import aiohttp
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(dotenv_path="src/.env")

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.logger.logger_handler import get_logger
from src.domain.dto.insert_category_dto import InsertCategoryDto
from src.domain.dto.insert_category_tags_dto import InsertCategoryTagsDTO
from src.service.crawl.insert_crawled import insert_category, insert_category_tags, insert_tags
from src.service.crawl.update_crawled import update_category, update_category_tags
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository

# 로거 초기화
logger = get_logger('crawling_naver')


class CategoryTypeClassifier:
    """LLM을 사용하여 서브 카테고리를 분류하는 클래스"""
    
    def __init__(self):
        self.api_token = os.getenv('COPILOT_API_KEY') or os.getenv('GITHUB_TOKEN')
        if self.api_token:
            self.api_endpoint = "https://api.githubcopilot.com/chat/completions"
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        else:
            logger.warning("GitHub API 토큰이 없습니다. 카테고리 분류 기능이 비활성화됩니다.")
    
    async def classify_category_type(self, sub_category: str, max_retries: int = 5) -> int:
        """
        서브 카테고리를 LLM으로 분석하여 타입 결정
        
        Args:
            sub_category: 서브 카테고리 (예: "일식", "카페", "박물관" 등)
            max_retries: 최대 재시도 횟수
            
        Returns:
            int: 0 (음식점), 1 (카페), 2 (콘텐츠), 3 (기타)
        """
        if not self.api_token:
            logger.warning("API 토큰이 없어 기본값 3을 반환합니다.")
            return 3
        
        if not sub_category or not sub_category.strip():
            logger.warning("서브 카테고리가 비어있어 기본값 3을 반환합니다.")
            return 3
        
        prompt = f"""다음 카테고리를 분석하여 숫자로만 답변하세요.

<카테고리>
{sub_category}

<분류 기준>
- 음식점 (한식, 일식, 중식, 양식, 분식, 치킨, 고기, 회, 뷔페, 술집 등) → 0
- 카페 (카페, 커피, 디저트, 베이커리, 빵집 등) → 1
- 콘텐츠 (관광지, 박물관, 미술관, 공원, 놀이공원, 체험관, 전시관, 테마파크 등) → 2
- 분류하기 힘든 경우 → 3

답변 (숫자만):"""
        
        payload = {
            "model": "gpt-4.1",
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 카테고리를 음식점(0), 카페(1), 콘텐츠(2), 기타(3)로 분류하는 전문가입니다. 반드시 0, 1, 2, 3 중 하나의 숫자만 답변하세요."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 10
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
                            category_type_str = result['choices'][0]['message']['content'].strip()
                            
                            # 숫자만 추출
                            category_type_str = re.sub(r'[^0-3]', '', category_type_str)
                            
                            if category_type_str in ['0', '1', '2', '3']:
                                category_type = int(category_type_str)
                                logger.info(f"카테고리 분류 완료: '{sub_category}' → 타입 {category_type}")
                                return category_type
                            else:
                                logger.warning(f"유효하지 않은 응답: {category_type_str}, 기본값 3 반환")
                                return 3
                        else:
                            logger.warning(f"✗ 카테고리 분류 API 호출 실패 ({attempt}번째 시도) - 상태 코드: {response.status}")
                            
                            if attempt < max_retries:
                                await asyncio.sleep(2)
                            else:
                                logger.error(f"✗ 최대 재시도 횟수({max_retries}회) 초과 - 기본값 3 반환")
                                return 3
                
            except asyncio.TimeoutError:
                logger.warning(f"✗ 카테고리 분류 API 시간 초과 ({attempt}번째 시도)")
                
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.error(f"✗ 최대 재시도 횟수({max_retries}회) 초과 - 기본값 3 반환")
                    return 3
                    
            except Exception as e:
                logger.error(f"✗ 카테고리 분류 중 오류 ({attempt}번째 시도): {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.error(f"✗ 최대 재시도 횟수({max_retries}회) 초과 - 기본값 3 반환")
                    return 3
        
        return 3


class GeocodingService:
    """카카오 로컬 API를 사용한 주소 -> 좌표 변환 서비스"""
    
    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: 카카오 REST API 키
        """
        self.api_key = api_key or os.getenv('KAKAO_REST_API_KEY')
        
        if not self.api_key:
            logger.warning("카카오 REST API 키가 없습니다. 좌표 변환 기능이 비활성화됩니다.")
        
        self.base_url = "https://dapi.kakao.com/v2/local/search/address.json"
        self.headers = {
            "Authorization": f"KakaoAK {self.api_key}"
        }
    
    async def get_coordinates(self, address: str, max_retries: int = 5) -> Tuple[Optional[str], Optional[str]]:
        """
        주소를 좌표(경도, 위도)로 변환 (비동기)
        
        Args:
            address: 변환할 주소
            max_retries: 최대 재시도 횟수
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (경도, 위도) 또는 (None, None)
        """
        if not self.api_key:
            logger.warning("API 키가 없어 좌표 변환을 건너뜁니다.")
            return None, None
        
        if not address or not address.strip():
            logger.warning("주소가 비어있습니다.")
            return None, None
        
        params = {
            "query": address
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        self.base_url,
                        headers=self.headers,
                        params=params
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            
                            if result.get('documents') and len(result['documents']) > 0:
                                doc = result['documents'][0]
                                longitude = str(doc['x'])  # 경도 (문자열로 변환)
                                latitude = str(doc['y'])   # 위도 (문자열로 변환)
                                
                                return longitude, latitude
                            else:
                                logger.warning(f"주소에 대한 좌표를 찾을 수 없습니다: {address}")
                                return None, None
                                
                        elif response.status == 401:
                            logger.error("카카오 API 인증 실패. API 키를 확인하세요.")
                            return None, None
                            
                        else:
                            logger.warning(f"✗ 좌표 변환 실패 ({attempt}번째 시도) - 상태 코드: {response.status}")
                            
                            if attempt < max_retries:
                                await asyncio.sleep(3)
                            else:
                                logger.error(f"✗ 최대 재시도 횟수 초과")
                                return None, None
                        
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(1)
                else:
                    logger.error(f"✗ 최대 재시도 횟수 초과")
                    return None, None
                    
            except Exception as e:
                logger.error(f"✗ 좌표 변환 중 오류 ({attempt}번째 시도): {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(1)
                else:
                    return None, None
        
        return None, None


class AddressParser:
    """주소 파싱 유틸리티 클래스"""
    
    @staticmethod
    def parse_address(full_address: str) -> Tuple[str, str, str, str]:
        """
        전체 주소를 do, si, gu, detail_address로 분리
        
        Args:
            full_address: 전체 주소 (예: "서울 마포구 양화로 144")
            
        Returns:
            Tuple[str, str, str, str]: (do, si, gu, detail_address)
        """
        if not full_address:
            return "", "", "", ""
        
        try:
            do = ""
            si = ""
            gu = ""
            detail_address = ""
            
            logger.info(f"원본 주소: {full_address}")
            
            # 특별시/광역시 매핑 (do 없이 si에만 들어감)
            city_mapping = {
                '서울': '서울특별시',
                '부산': '부산광역시',
                '대구': '대구광역시',
                '인천': '인천광역시',
                '광주': '광주광역시',
                '대전': '대전광역시',
                '울산': '울산광역시',
                '세종': '세종특별자치시'
            }
            
            # 1단계: 특별시/광역시 처리 (공백 기준)
            parts = full_address.split(maxsplit=1)
            
            if parts:
                first_word = parts[0]
                
                # 특별시/광역시 약칭인 경우
                if first_word in city_mapping:
                    si = city_mapping[first_word]
                    remaining = parts[1] if len(parts) > 1 else ""
                # "서울특별시" 같이 전체 이름으로 온 경우
                elif any(first_word.endswith(suffix) for suffix in ['특별시', '광역시', '특별자치시']):
                    si = first_word
                    remaining = parts[1] if len(parts) > 1 else ""
                # "경기도", "전라남도" 등 도 단위
                elif first_word.endswith('도') or first_word.endswith('특별자치도'):
                    do = first_word
                    remaining = parts[1] if len(parts) > 1 else ""
                else:
                    remaining = full_address
            else:
                remaining = full_address
            
            # 2단계: do가 있는 경우에만 si 추출
            if do and not si:
                si_parts = remaining.split(maxsplit=1)
                if si_parts:
                    first_part = si_parts[0]
                    if first_part.endswith('시') or first_part.endswith('군'):
                        si = first_part
                        remaining = si_parts[1] if len(si_parts) > 1 else ""
            
            # 3단계: 구/읍/면 추출 (공백 기준)
            gu_parts = remaining.split(maxsplit=1)
            if gu_parts:
                first_part = gu_parts[0]
                if first_part.endswith('구') or first_part.endswith('읍') or first_part.endswith('면'):
                    gu = first_part
                    detail_address = gu_parts[1] if len(gu_parts) > 1 else ""
                else:
                    detail_address = remaining
            else:
                detail_address = remaining
            
            logger.info(f"주소 파싱 결과:")
            logger.info(f"  - do: '{do}' (NULL: {not do})")
            logger.info(f"  - si: '{si}' (NULL: {not si})")
            logger.info(f"  - gu: '{gu}' (NULL: {not gu})")
            logger.info(f"  - detail: '{detail_address}'")
            
            return do, si, gu, detail_address
            
        except Exception as e:
            logger.error(f"주소 파싱 중 오류: {e}")
            return "", "", "", full_address


class NaverMapFavoriteCrawler:
    """네이버 지도 즐겨찾기 목록 크롤링을 위한 클래스"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.geocoding_service = GeocodingService()
        self.category_classifier = CategoryTypeClassifier()
        
    async def _save_store_data(self, idx: int, total: int, store_data: Tuple, place_name: str):
        """
        크롤링한 데이터를 DB에 저장하는 비동기 함수
        
        Args:
            idx: 현재 인덱스
            total: 전체 개수
            store_data: 크롤링한 상점 데이터
            place_name: 장소명
            
        Returns:
            Tuple[bool, str]: (성공 여부, 로그 메시지)
        """
        try:
            name, full_address, phone, business_hours, image, sub_category, tag_reviews = store_data
            
            # 주소 파싱
            do, si, gu, detail_address = AddressParser.parse_address(full_address)
            
            # 좌표 변환과 카테고리 분류를 병렬로 실행
            (longitude, latitude), category_type = await asyncio.gather(
                self.geocoding_service.get_coordinates(full_address),
                self.category_classifier.classify_category_type(sub_category)
            )
            
            # DTO 생성
            category_dto = InsertCategoryDto(
                name=name,
                do=do,
                si=si,
                gu=gu,
                detail_address=detail_address,
                sub_category=sub_category,
                business_hour=business_hours or "",
                phone=phone.replace('-', '') if phone else "",
                type=category_type,
                image=image or "",
                latitude=latitude or "",
                longitude=longitude or ""
            )
            
            # category 저장
            # 1. 먼저 DB에서 중복 체크 (name, type, detail_address로 조회)
            category_repository = CategoryRepository()
            existing_categories = await category_repository.select_by(
                name=name,
                type=category_type,
                detail_address=detail_address
            )
            
            category_id = None
            
            # 2. 중복 데이터가 있으면 update, 없으면 insert
            if len(existing_categories) == 1:
                # 기존 데이터 업데이트
                logger.info(f"[저장 {idx+1}/{total}] 기존 카테고리 발견 - 업데이트 모드: {name}")
                category_id = await update_category(category_dto)
            elif len(existing_categories) == 0:
                # 새로운 데이터 삽입
                logger.info(f"[저장 {idx+1}/{total}] 신규 카테고리 - 삽입 모드: {name}")
                category_id = await insert_category(category_dto)
            else:
                # 중복이 2개 이상인 경우 (데이터 무결성 문제)
                logger.error(f"[저장 {idx+1}/{total}] 중복 카테고리가 {len(existing_categories)}개 발견됨: {name}")
                raise Exception(f"중복 카테고리 데이터 무결성 오류: {name}")
            
            if category_id:
                # 태그 리뷰 저장
                tag_success_count = 0
                for tag_name, tag_count in tag_reviews:
                    try:
                        # tags 테이블에 저장 또는 가져오기
                        tag_id = await insert_tags(tag_name, category_type)
                        
                        if tag_id:
                            # category_tags DTO 생성
                            category_tags_dto = InsertCategoryTagsDTO(
                                tag_id=tag_id,
                                category_id=category_id,
                                count=tag_count
                            )
                            
                            # 3. category_tags도 중복 체크
                            category_tags_repository = CategoryTagsRepository()
                            existing_tags = await category_tags_repository.select_by(
                                tag_id=tag_id,
                                category_id=category_id
                            )
                            
                            # 중복이면 update, 아니면 insert
                            if len(existing_tags) == 1:
                                if await update_category_tags(category_tags_dto):
                                    tag_success_count += 1
                            elif len(existing_tags) == 0:
                                if await insert_category_tags(category_tags_dto):
                                    tag_success_count += 1
                            else:
                                logger.error(f"중복 태그가 {len(existing_tags)}개 발견됨")
                                
                    except Exception as tag_error:
                        logger.error(f"태그 저장 중 오류: {tag_name} - {tag_error}")
                        continue
                
                type_names = {0: '음식점', 1: '카페', 2: '콘텐츠', 3: '기타'}
                success_msg = (
                    f"✓ [저장 {idx+1}/{total}] '{name}' 완료\n"
                    f"  - 서브 카테고리: {sub_category}\n"
                    f"  - 타입: {type_names.get(category_type, '기타')} ({category_type})\n"
                    f"  - 태그 리뷰: {tag_success_count}/{len(tag_reviews)}개 저장"
                )
                logger.info(success_msg)
                return True, success_msg
            else:
                error_msg = f"✗ [저장 {idx+1}/{total}] '{name}' DB 저장 실패"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as db_error:
            error_msg = f"✗ [저장 {idx+1}/{total}] '{place_name}' DB 저장 중 오류: {db_error}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            return False, error_msg
        
    async def crawl_favorite_list(self, favorite_url: str, delay: int = 20, output_file: str = None):
        """
        네이버 지도 즐겨찾기 목록에서 장소들을 크롤링
        크롤링과 저장을 분리하여 병렬 처리
        
        Args:
            favorite_url: 즐겨찾기 URL
            delay: 각 장소 크롤링 사이의 대기 시간(초)
            output_file: 결과 저장 파일 (선택)
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            
            try:
                # 즐겨찾기 페이지로 이동
                logger.info(f"즐겨찾기 페이지로 이동: {favorite_url}")
                await page.goto(favorite_url, wait_until='domcontentloaded', timeout=60000)
                logger.info("페이지 로딩 대기 중...")
                await asyncio.sleep(10)
                
                # myPlaceBookmarkListIframe 대기
                logger.info("myPlaceBookmarkListIframe 대기 중...")
                try:
                    await page.wait_for_selector('iframe#myPlaceBookmarkListIframe', timeout=30000)
                except Exception as e:
                    logger.error(f"iframe을 찾을 수 없습니다: {e}")
                    html = await page.content()
                    with open('debug_main_page.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    logger.info("debug_main_page.html 파일에 페이지 내용을 저장했습니다.")
                    return
                
                # iframe 가져오기
                list_frame_locator = page.frame_locator('iframe#myPlaceBookmarkListIframe')
                list_frame = page.frame('myPlaceBookmarkListIframe')
                
                if not list_frame:
                    logger.error("myPlaceBookmarkListIframe을 찾을 수 없습니다.")
                    return
                
                logger.info("✓ myPlaceBookmarkListIframe 발견")
                await asyncio.sleep(3)
                
                # 여러 가능한 선택자 시도
                possible_selectors = [
                    '#app > div > div:nth-child(3) > div > ul > li',
                    'ul.list_place > li',
                    'ul > li',
                    '[role="list"] > *',
                ]
                
                place_selector = None
                
                # iframe 내부에서 선택자 찾기
                for selector in possible_selectors:
                    try:
                        logger.info(f"선택자 시도: {selector}")
                        elements = await list_frame_locator.locator(selector).all()
                        if len(elements) > 0:
                            place_selector = selector
                            logger.info(f"✓ 선택자 발견: {selector} - {len(elements)}개 요소")
                            break
                    except Exception as e:
                        logger.warning(f"✗ 선택자 없음: {selector} - {e}")
                        continue
                
                if not place_selector:
                    html_content = await list_frame.content()
                    with open('debug_iframe.html', 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.error("장소 목록 선택자를 찾을 수 없습니다. debug_iframe.html 파일을 확인하세요.")
                    return
                
                # 스크롤하여 모든 장소 로드
                logger.info("스크롤하여 모든 장소 로드 중...")
                await self._scroll_to_load_all_places(list_frame_locator, place_selector)
                
                # 최종 장소 개수 확인
                places = await list_frame_locator.locator(place_selector).all()
                total = len(places)
                
                if total == 0:
                    logger.warning("크롤링할 장소가 없습니다.")
                    return
                
                logger.info(f"총 {total}개 장소 크롤링 시작")
                logger.info("=" * 60)
                
                success_count = 0
                fail_count = 0
                
                # 저장 태스크를 담을 리스트
                save_tasks = []
                
                # 각 장소 크롤링
                for idx in range(total):
                    try:
                        # 매번 목록을 다시 가져와야 함 (DOM이 변경되기 때문)
                        places = await list_frame_locator.locator(place_selector).all()
                        
                        if idx >= len(places):
                            logger.error(f"[크롤링 {idx+1}/{total}] 장소 인덱스가 범위를 벗어났습니다.")
                            fail_count += 1
                            continue
                        
                        place = places[idx]
                        
                        # 장소명 미리 가져오기 (로깅용)
                        try:
                            name_selectors = ['div.name', 'span.name', '.place_name', 'a.name', '.item_name', 'span']
                            place_name = None
                            
                            for name_sel in name_selectors:
                                try:
                                    place_name = await place.locator(name_sel).first.inner_text(timeout=2000)
                                    if place_name and place_name.strip():
                                        break
                                except:
                                    continue
                            
                            if not place_name:
                                place_name = f"장소 {idx+1}"
                        except:
                            place_name = f"장소 {idx+1}"
                        
                        # 장소 클릭
                        logger.info(f"[크롤링 {idx+1}/{total}] '{place_name}' 클릭 중...")

                        # 클릭 가능한 요소 찾기
                        try:
                            clickable = place.locator('div, li[role="button"]').first
                            await clickable.click(timeout=5000)
                        except:
                            await place.click(timeout=5000)

                        await asyncio.sleep(3)

                        # 폐업 팝업 체크
                        logger.info(f"[크롤링 {idx+1}/{total}] 폐업 팝업 체크 중...")

                        popup_selectors = [
                            'body > div:nth-child(4) > div._show_62e0u_8',
                            'div._show_62e0u_8',
                            'div._popup_62e0u_1._show_62e0u_8',
                            'div[class*="_show_"]',
                            'div._popup_62e0u_1',
                        ]

                        is_popup_found = False
                        popup_element = None

                        for popup_selector in popup_selectors:
                            try:
                                popup_element = list_frame_locator.locator(popup_selector).first
                                is_visible = await popup_element.is_visible(timeout=1000)
                                
                                if is_visible:
                                    logger.warning(f"⚠ [크롤링 {idx+1}/{total}] '{place_name}' 폐업 팝업 감지! (셀렉터: {popup_selector})")
                                    is_popup_found = True
                                    break
                            except Exception as e:
                                logger.debug(f"  셀렉터 '{popup_selector}' 실패: {e}")
                                continue

                        if is_popup_found:
                            # 확인 버튼 클릭
                            button_selectors = [
                                'body > div:nth-child(4) > div > div._popup_62e0u_1._at_pc_62e0u_21._show_62e0u_8 > div._popup_buttons_62e0u_85 > button'
                            ]
                            
                            button_clicked = False
                            for button_selector in button_selectors:
                                try:
                                    popup_button = list_frame_locator.locator(button_selector).first
                                    if await popup_button.is_visible(timeout=1000):
                                        await popup_button.click(timeout=2000)
                                        await asyncio.sleep(0.5)
                                        logger.info(f"✓ 폐업 팝업 닫기 완료 (버튼 셀렉터: {button_selector})")
                                        button_clicked = True
                                        break
                                except Exception as e:
                                    logger.debug(f"  버튼 셀렉터 '{button_selector}' 실패: {e}")
                                    continue
                            
                            if not button_clicked:
                                logger.error("✗ 팝업 닫기 버튼을 찾을 수 없습니다")
                            
                            fail_count += 1
                            
                            # 마지막 장소가 아니면 딜레이
                            if idx < total - 1:
                                logger.info(f"[대기] {delay}초 대기 중...")
                                await asyncio.sleep(delay)
                            
                            continue  # 다음 장소로 건너뛰기

                        logger.info(f"[크롤링 {idx+1}/{total}] 팝업 없음 - 정상 크롤링 진행")

                        # entry iframe 가져오기 (메인 페이지에서)
                        entry_frame = await self._get_entry_frame(page)

                        if not entry_frame:
                            logger.error(f"[크롤링 {idx+1}/{total}] entry iframe을 찾을 수 없습니다.")
                            fail_count += 1
                            continue

                        # 상세 정보 추출
                        extractor = StoreDetailExtractor(entry_frame, page)
                        store_data = await extractor.extract_all_details()
                        
                        if store_data:
                            logger.info(f"✓ [크롤링 {idx+1}/{total}] '{place_name}' 크롤링 완료")
                            
                            # 저장 태스크 생성 (백그라운드에서 실행)
                            save_task = asyncio.create_task(
                                self._save_store_data(idx, total, store_data, place_name)
                            )
                            save_tasks.append(save_task)
                            
                            # 크롤링 완료 후 바로 delay 시작
                            if idx < total - 1:
                                logger.info(f"[대기] {delay}초 대기 중... (저장은 백그라운드에서 진행)")
                                await asyncio.sleep(delay)
                            
                        else:
                            fail_count += 1
                            logger.error(f"✗ [크롤링 {idx+1}/{total}] 상점 정보 추출 실패")
                            
                            # 실패해도 딜레이
                            if idx < total - 1:
                                logger.info(f"[대기] {delay}초 대기 중...")
                                await asyncio.sleep(delay)
                        
                    except Exception as e:
                        fail_count += 1
                        logger.error(f"✗ [크롤링 {idx+1}/{total}] 크롤링 중 오류: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        
                        # 오류가 발생해도 딜레이
                        if idx < total - 1:
                            logger.info(f"[대기] {delay}초 대기 중...")
                            await asyncio.sleep(delay)
                        continue
                
                # 모든 크롤링이 끝난 후 저장 태스크들이 완료될 때까지 대기
                logger.info("=" * 60)
                logger.info(f"모든 크롤링 완료! 저장 작업 완료 대기 중... ({len(save_tasks)}개)")
                logger.info("=" * 60)
                
                if save_tasks:
                    save_results = await asyncio.gather(*save_tasks, return_exceptions=True)
                    
                    # 저장 결과 집계
                    for result in save_results:
                        if isinstance(result, Exception):
                            fail_count += 1
                        elif isinstance(result, tuple):
                            success, msg = result
                            if success:
                                success_count += 1
                            else:
                                fail_count += 1
                
                logger.info("=" * 60)
                logger.info(f"전체 작업 완료: 성공 {success_count}/{total}, 실패 {fail_count}/{total}")
                logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"즐겨찾기 크롤링 중 오류: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                await browser.close()
    
    async def _scroll_to_load_all_places(self, frame_locator, place_selector: str):
        """
        iframe 내부를 스크롤하여 모든 장소를 로드
        
        Args:
            frame_locator: iframe locator
            place_selector: 장소 선택자
        """
        logger.info("스크롤 시작...")
        
        # 스크롤 컨테이너 찾기 (여러 가능한 선택자 시도)
        scroll_container_selectors = [
            '#app > div > div:nth-child(3)',
            '#app > div > div:nth-child(3) > div',
            'div[class*="scroll"]',
            'div[style*="overflow"]',
        ]
        
        prev_count = 0
        same_count = 0
        max_same_count = 3
        
        for scroll_attempt in range(500):
            try:
                # 현재 장소 개수
                places = await frame_locator.locator(place_selector).all()
                current_count = len(places)
                
                logger.info(f"스크롤 {scroll_attempt + 1}회: {current_count}개 장소 발견")
                
                # 개수가 같으면 카운트 증가
                if current_count == prev_count:
                    same_count += 1
                    if same_count >= max_same_count:
                        logger.info(f"✓ 스크롤 완료: 총 {current_count}개 장소")
                        break
                else:
                    same_count = 0
                
                prev_count = current_count
                
                # 마지막 요소로 스크롤
                if current_count > 0:
                    last_place = frame_locator.locator(place_selector).nth(current_count - 1)
                    try:
                        await last_place.scroll_into_view_if_needed(timeout=3000)
                    except:
                        pass
                
                # 스크롤 컨테이너에서 직접 스크롤 시도
                for container_selector in scroll_container_selectors:
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
        
        logger.info("✓ 스크롤 완료")
    
    async def _get_entry_frame(self, page: Page):
        """상세 정보 iframe 가져오기"""
        try:
            await page.wait_for_selector('iframe#entryIframe', timeout=10000)
            entry_frame = page.frame_locator('iframe#entryIframe')
            await asyncio.sleep(3)
            return entry_frame
        except TimeoutError:
            logger.error("entryIframe을 찾을 수 없습니다.")
            return None


class StoreDetailExtractor:
    """상점 상세 정보 추출을 위한 클래스"""
    
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
        모든 상세 정보 추출 (태그 리뷰 포함)
        
        Returns:
            Tuple: (name, full_address, phone, business_hours, image, sub_category, tag_reviews)
            tag_reviews: List[Tuple[str, int]] - [(태그명, 선택횟수), ...]
        """
        
        try:
            # 기본 정보 추출
            name = await self._extract_title()
            full_address = await self._extract_address()
            phone = await self._extract_phone()
            business_hours = await self._extract_business_hours()
            image = await self._extract_image()
            sub_category = await self._extract_sub_category()
            
            # 리뷰 탭으로 이동하여 태그 리뷰 추출
            tag_reviews = await self._extract_tag_reviews()
            
            logger.info(f"상점 정보 추출 완료: {name}")
            logger.info(f"  - 주소: {full_address}")
            logger.info(f"  - 서브 카테고리: {sub_category}")
            logger.info(f"  - 태그 리뷰: {len(tag_reviews)}개")
            
            return (name, full_address, phone, business_hours, image, sub_category, tag_reviews)
            
        except Exception as e:
            logger.error(f"상점 정보 추출 중 오류: {e}")
            return None
    
    async def _extract_title(self) -> str:
        """매장명 추출"""
        try:
            name_locator = self.frame.locator('span.GHAhO')
            title = await name_locator.inner_text(timeout=5000)
            return title
        except TimeoutError:
            logger.error(f"매장명 추출 Timeout")
            return ""
        except Exception as e:
            logger.error(f"매장명 추출 오류: {e}")
            return ""
    
    async def _extract_address(self) -> Optional[str]:
        """주소 추출 (지번 주소 버튼 클릭 후 가져오기)"""
        try:
            # 주소 영역까지 스크롤
            address_section = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D')
            await address_section.scroll_into_view_if_needed()
            await asyncio.sleep(1)
            
            # 주소 버튼 대기 및 클릭
            address_button = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D > div > a')
            
            # 버튼이 보일 때까지 대기
            await address_button.wait_for(state='visible', timeout=5000)
            await asyncio.sleep(0.5)
            
            # 버튼 클릭
            await address_button.click()
            logger.info("주소 버튼 클릭 완료")
            await asyncio.sleep(2)
            
            # 지번 주소 div 대기
            jibun_address_div = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D > div > div.Y31Sf > div:nth-child(2)')
            await jibun_address_div.wait_for(state='visible', timeout=5000)
            
            # JavaScript로 직접 텍스트 노드만 추출 (span 제외)
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
            
            logger.info(f"지번 주소 추출 완료: {jibun_address}")
            
            # 버튼 다시 클릭하여 닫기
            try:
                await address_button.click()
                await asyncio.sleep(0.5)
                logger.info("주소 팝업 닫기 완료")
            except:
                pass
            
            return jibun_address
            
        except TimeoutError:
            logger.error(f"주소 추출 Timeout")
            
            # 기본 주소 시도
            try:
                fallback_locator = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D > div > a > span.LDgIH')
                fallback_address = await fallback_locator.inner_text(timeout=3000)
                logger.info(f"기본 주소 사용: {fallback_address}")
                return fallback_address
            except:
                logger.error("기본 주소도 추출 실패")
                return ""
                
        except Exception as e:
            logger.error(f"주소 추출 오류: {e}")
            
            # 기본 주소 시도
            try:
                fallback_locator = self.frame.locator('div.place_section_content > div > div.O8qbU.tQY7D > div > a > span.LDgIH')
                fallback_address = await fallback_locator.inner_text(timeout=3000)
                logger.info(f"기본 주소 사용: {fallback_address}")
                return fallback_address
            except:
                logger.error("기본 주소도 추출 실패")
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
    
    async def _extract_sub_category(self) -> str:
        """서브 카테고리 추출"""
        try:
            sub_category_locator = self.frame.locator('#_title > div > span.lnJFt')
            sub_category = await sub_category_locator.inner_text(timeout=5000)
            logger.info(f"서브 카테고리 추출: {sub_category}")
            return sub_category
        except TimeoutError:
            logger.error(f"서브 카테고리 추출 Timeout")
            return ""
        except Exception as e:
            logger.error(f"서브 카테고리 추출 오류: {e}")
            return ""
    
    async def _extract_business_hours(self) -> str:
        """영업시간 추출 및 LLM으로 정리"""
        try:
            business_hours_button = self.frame.locator('div.O8qbU.pSavy a').first
            
            if await business_hours_button.is_visible(timeout=5000):
                # 영업시간 버튼까지 스크롤
                await business_hours_button.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                
                # 버튼 클릭
                await business_hours_button.click()
                await asyncio.sleep(1)
                
                business_hours_locators = self.frame.locator('div.O8qbU.pSavy div.w9QyJ')
                hours_list = await business_hours_locators.all_inner_texts()
                
                if hours_list:
                    raw_hours = "\n".join(hours_list)
                    logger.info(f"원본 영업시간 추출: {raw_hours}")
                    
                    # LLM으로 영업시간 정리
                    cleaned_hours = await self._clean_business_hours_with_llm(raw_hours)
                    logger.info(f"정리된 영업시간: {cleaned_hours}")
                    return cleaned_hours
                else:
                    return ""
            else:
                logger.error(f"영업시간 추출 실패")
                return ""
        except Exception as e:
            logger.error(f"영업시간 추출 오류: {e}")
            return ""
    
    async def _clean_business_hours_with_llm(self, raw_hours: str, max_retries: int = 10) -> str:
        """LLM을 사용하여 영업시간 데이터를 정리 (비동기)"""
        if not self.api_token:
            logger.warning("API 토큰이 없어 영업시간을 정리하지 못했습니다.")
            return raw_hours
        
        if not raw_hours or not raw_hours.strip():
            return ""
        
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
                {
                    "role": "system",
                    "content": "당신은 상점 영업시간 정보를 간결하게 정리하는 전문가입니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
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
                            cleaned_hours = result['choices'][0]['message']['content'].strip()
                            return cleaned_hours
                        else:
                            if response.status != 403:
                                logger.warning(f"✗ 영업시간 정리 API 호출 실패 ({attempt}번째 시도) - 상태 코드: {response.status}")
                            
                            if attempt < max_retries:
                                await asyncio.sleep(2)
                            else:
                                logger.error(f"✗ 최대 재시도 횟수({max_retries}회) 초과 - 원본 반환")
                                return raw_hours
                
            except asyncio.TimeoutError:
                logger.warning(f"✗ 영업시간 정리 API 시간 초과 ({attempt}번째 시도)")
                
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.error(f"✗ 최대 재시도 횟수({max_retries}회) 초과 - 원본 반환")
                    return raw_hours
                    
            except Exception as e:
                logger.error(f"✗ 영업시간 정리 중 오류 ({attempt}번째 시도): {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.error(f"✗ 최대 재시도 횟수({max_retries}회) 초과 - 원본 반환")
                    return raw_hours
        
        return raw_hours
    
    async def _extract_image(self) -> Optional[str]:
        """이미지 URL 추출"""
        try:
            # 첫 번째 선택자 시도
            first_selector = 'div[role="main"] > div > div > a > img'
            first_image = self.frame.locator(first_selector).first
            
            if await first_image.count() > 0:
                src = await first_image.get_attribute('src', timeout=5000)
                if src:
                    return src
            
            # 두 번째 선택자 시도
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
    
    async def _extract_tag_reviews(self) -> List[Tuple[str, int]]:
        """
        리뷰 탭에서 태그 리뷰 추출
        
        Returns:
            List[Tuple[str, int]]: [(태그명, 선택횟수), ...]
        """
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
                except TimeoutError:
                    break
            
            # 태그 리뷰 추출
            opinion_elements = await self.frame.locator('div.mrSZf > ul > li').all()
            
            for opinion_element in opinion_elements:
                try:
                    review_tag = await opinion_element.locator('span.t3JSf').inner_text(timeout=3000)
                    rating = await opinion_element.locator('span.CUoLy').inner_text(timeout=3000)
                    cleaned_rating = int(re.sub(r'이 키워드를 선택한 인원\n', '', rating).replace(',', ''))
                    tag_reviews.append((review_tag, cleaned_rating))
                except (TimeoutError, ValueError) as e:
                    logger.error(f"리뷰 태그 또는 평점 추출 중 오류: {e}")
                    continue
            
            logger.info(f"태그 리뷰 {len(tag_reviews)}개 추출 완료")
            
        except Exception as e:
            logger.error(f"태그 리뷰 추출 중 오류: {e}")
        
        return tag_reviews


async def main(favorite_url = 'https://map.naver.com/p/favorite/sSjt-6mGnGEqi8HA:2D_MP7QkdZtDuASbcBgfEqXAYqV5Tw/folder/723cd582cd1e43dcac5234ad055c7494/pc/place/1477750254?c=10.15,0,0,0,dh&placePath=/home?from=map&fromPanelNum=2&timestamp=202510210943&locale=ko&svcName=map_pcv5'):
    """메인 함수"""
    
    # 크롤러 생성
    crawler = NaverMapFavoriteCrawler(headless=False)
    
    # 즐겨찾기 목록 크롤링
    await crawler.crawl_favorite_list(
        favorite_url=favorite_url,
        delay=30,
        output_file=None
    )

if __name__ == "__main__":
    asyncio.run(main("https://map.naver.com/p/favorite/sSjt-6mGnGEqi8HA:2D_MP7QkdZtDuASbcBgfEqXAYqV5Tw/folder/723cd582cd1e43dcac5234ad055c7494/pc/place/1477750254?c=10.15,0,0,0,dh&placePath=/home?from=map&fromPanelNum=2&timestamp=202510210943&locale=ko&svcName=map_pcv5"))