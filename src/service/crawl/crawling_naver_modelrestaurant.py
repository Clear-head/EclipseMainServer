import json
import asyncio
from playwright.async_api import async_playwright, TimeoutError, Page
import re
from typing import Optional, List, Tuple
import sys, os
import datetime
import pymysql
import requests
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(dotenv_path="src/.env")

# DB 설정 (기존 original_data 테이블용)
db_config = {
    'host': 'localhost',
    'port': 3310,
    'user': 'root',
    'password': '1234',
    'database': 'eclipse2',
    'charset': 'utf8mb4'
}

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from logger.logger_handler import get_logger

# 로거 초기화
logger = get_logger('crawling_naver')


class GangnamAPIService:
    """강남구 모범음식점 API 서비스"""
    
    def __init__(self):
        self.base_url = 'http://openAPI.gangnam.go.kr:8088/6c5a686c7463736833317a72696142/json/GnModelRestaurantDesignate'
    
    def fetch_all_restaurants(self) -> List[dict]:
        """
        강남구 모범음식점 API에서 모든 데이터 가져오기
        
        Returns:
            List[dict]: 음식점 데이터 리스트
        """
        try:
            # 전체 개수 확인
            response = requests.get(f'{self.base_url}/1/1/')
            data = response.json()
            total_count = data['GnModelRestaurantDesignate']['list_total_count']
            logger.info(f"강남구 모범음식점 전체 개수: {total_count}개")
            
            # 모든 데이터 수집
            all_data = []
            batch_size = 1000
            
            for start in range(1, total_count + 1, batch_size):
                end = min(start + batch_size - 1, total_count)
                logger.info(f"API 데이터 수집 중... {start}~{end}")
                
                url = f'{self.base_url}/{start}/{end}/'
                response = requests.get(url)
                
                if response.status_code == 200:
                    batch_data = response.json()
                    if 'GnModelRestaurantDesignate' in batch_data and 'row' in batch_data['GnModelRestaurantDesignate']:
                        rows = batch_data['GnModelRestaurantDesignate']['row']
                        all_data.extend(rows)
                else:
                    logger.error(f"API 호출 오류: {response.status_code}")
            
            logger.info(f"총 {len(all_data)}개 데이터 수집 완료")
            return all_data
            
        except Exception as e:
            logger.error(f"강남구 API 데이터 수집 중 오류: {e}")
            return []
    
    def convert_to_store_format(self, api_data: List[dict]) -> List[dict]:
        """
        API 데이터를 크롤링용 포맷으로 변환
        
        Args:
            api_data: API에서 가져온 원본 데이터
            
        Returns:
            List[dict]: 변환된 상점 데이터 (id, name, address, sub_category, type, admdng_nm)
        """
        converted_data = []
        
        for idx, row in enumerate(api_data, 1):
            store = {
                'id': idx,
                'name': row.get('UPSO_NM', '').strip(),
                'address': row.get('SITE_ADDR', '').strip(),  # 지번 주소 사용
                'sub_category': row.get('SNT_UPTAE_NM', '').strip(),
                'type': 0,  # 음식점으로 설정
                'admdng_nm': row.get('ADMDNG_NM', '').strip(),  # 행정동명
                'main_edf': row.get('MAIN_EDF', '').strip(),  # 대표메뉴
                'original_data': row  # 원본 데이터 보관
            }
            converted_data.append(store)
        
        return converted_data


class GeocodingService:
    """카카오 로컬 API를 사용한 주소 -> 좌표 변환 서비스"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('KAKAO_REST_API_KEY')
        
        if not self.api_key:
            logger.warning("카카오 REST API 키가 없습니다. 좌표 변환 기능이 비활성화됩니다.")
        
        self.base_url = "https://dapi.kakao.com/v2/local/search/address.json"
        self.headers = {
            "Authorization": f"KakaoAK {self.api_key}"
        }
    
    def get_coordinates(self, address: str, max_retries: int = 5) -> Tuple[Optional[float], Optional[float]]:
        """주소를 좌표(경도, 위도)로 변환"""
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
                response = requests.get(
                    self.base_url,
                    headers=self.headers,
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get('documents') and len(result['documents']) > 0:
                        doc = result['documents'][0]
                        longitude = float(doc['x'])
                        latitude = float(doc['y'])
                        return longitude, latitude
                    else:
                        logger.warning(f"주소에 대한 좌표를 찾을 수 없습니다: {address}")
                        return None, None
                        
                elif response.status_code == 401:
                    logger.error("카카오 API 인증 실패. API 키를 확인하세요.")
                    return None, None
                    
                else:
                    logger.warning(f"✗ 좌표 변환 실패 ({attempt}번째 시도) - 상태 코드: {response.status_code}")
                    
                    if attempt < max_retries:
                        asyncio.sleep(3)
                    else:
                        logger.error(f"✗ 최대 재시도 횟수 초과")
                        return None, None
                        
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    asyncio.sleep(1)
                else:
                    logger.error(f"✗ 최대 재시도 횟수 초과")
                    return None, None
                    
            except Exception as e:
                logger.error(f"✗ 좌표 변환 중 오류 ({attempt}번째 시도): {e}")
                
                if attempt < max_retries:
                    asyncio.sleep(1)
                else:
                    return None, None
        
        return None, None


class DatabaseManager:
    """데이터베이스 관리 클래스"""
    
    def __init__(self, config):
        self.config = config
    
    def get_connection(self):
        """DB 연결 생성"""
        return pymysql.connect(
            host=self.config['host'],
            port=self.config['port'],
            user=self.config['user'],
            password=self.config['password'],
            database=self.config['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    
    def _clean_utf8_string(self, text: str) -> str:
        """4바이트 UTF-8 문자 제거 (이모지 등)"""
        if not text:
            return text
        cleaned = text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
        cleaned = cleaned.replace('\n', ' ')
        return cleaned

    def _clean_json_data(self, data):
        """JSON 데이터에서 4바이트 문자 제거"""
        if isinstance(data, dict):
            return {key: self._clean_json_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._clean_json_data(item) for item in data]
        elif isinstance(data, str):
            return self._clean_utf8_string(data)
        else:
            return data
    
    def update_store(self, store_id: int, store_info: StoreInfo, longitude: float = None, latitude: float = None) -> bool:
        """
        크롤링한 상점 정보를 DB에 업데이트
        
        Args:
            store_id: 상점 ID
            store_info: 상점 정보 객체
            longitude: 경도
            latitude: 위도
        """
        connection = self.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    UPDATE original_data 
                    SET 
                        name = %s,
                        address = %s,
                        phone = %s,
                        business_hour = %s,
                        image = %s,
                        original_data = %s,
                        last_crawl = %s,
                        longitude = %s,
                        latitude = %s
                    WHERE id = %s
                """
                
                # 통합 태그만 저장
                original_data_json = {
                    'integrated_tags': store_info.blog_review_tags
                }
                
                # JSON 데이터 정제
                original_data_json = self._clean_json_data(original_data_json)
                original_data_str = json.dumps(original_data_json, ensure_ascii=False, default=str)
                original_data_str = self._clean_utf8_string(original_data_str)
                
                cursor.execute(sql, (
                    self._clean_utf8_string(store_info.title),
                    self._clean_utf8_string(store_info.address),
                    self._clean_utf8_string(store_info.phone),
                    self._clean_utf8_string(store_info.business_hours),
                    self._clean_utf8_string(store_info.image),
                    original_data_str,
                    store_info.last_crawl,
                    longitude,
                    latitude,
                    store_id
                ))
                connection.commit()
                
                coord_info = f"좌표: ({longitude}, {latitude})" if longitude and latitude else "좌표: 없음"
                logger.info(f"ID {store_id} 상점 정보가 DB에 업데이트되었습니다. {coord_info}")
                return True
        except Exception as e:
            logger.error(f"DB 업데이트 중 오류 (ID: {store_id}): {e}")
            connection.rollback()
            return False
        finally:
            connection.close()


class NaverMapSingleCrawler:
    """네이버 지도 단일 매장 크롤링을 위한 클래스"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.naver_map_url = "https://map.naver.com/v5/search"
        self.geocoding_service = GeocodingService()
        
    async def crawl(self, search_keyword: str, output_file: str = 'results.json', category: int = 0):
        """
        메인 크롤링 함수 - 단일 매장
        
        Args:
            search_keyword: 검색 키워드
            output_file: 결과 저장 파일
            category: 카테고리 (0: 음식점, 1: 카페, 2: 콘텐츠)
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            
            try:
                await self._navigate_to_naver_map(page)
                await self._search_keyword(page, search_keyword)
                
                entry_frame = await self._get_entry_frame(page)
                if not entry_frame:
                    logger.error(f"'{search_keyword}' 매장 정보를 찾을 수 없습니다.")
                    return None
                
                logger.info(f"'{search_keyword}' 크롤링 시작")
                
                place_info = await self._extract_store_details(entry_frame, search_keyword, page, category)
                if place_info:
                    if output_file:
                        self._save_single_store(output_file, place_info)
                    
                    logger.info(f"'{place_info.title}' 크롤링 완료")
                    return place_info
                else:
                    logger.error(f"'{search_keyword}' 매장 정보 추출 실패")
                    return None
                    
            except Exception as e:
                logger.error(f"'{search_keyword}' 크롤링 중 오류: {e}")
                return None
            finally:
                await browser.close()
    
    async def crawl_with_fallback(self, store_name: str, store_address: str, output_file: str = None, category: int = 0):
        """
        여러 검색 키워드 조합을 시도하여 크롤링
        1차: 지번주소(~동까지) + 가게명
        2차: 가게명만
        3차: 상세주소만
        4차: 상세주소 + 가게명
        
        Args:
            store_name: 상점명
            store_address: 상점 주소 (지번 주소)
            output_file: 결과 저장 파일 (선택)
            category: 카테고리
        """
        address_parts = store_address.split()
        
        # 1차 시도: 지번주소(~동까지) + 가게명
        if len(address_parts) >= 3:
            first_keyword = f"{self._extract_search_address(address_parts)} {store_name}"
        else:
            first_keyword = f"{store_address} {store_name}"
        
        result = await self.crawl(first_keyword, output_file, category=category)
        
        if result:
            return result
        
        await asyncio.sleep(4)
        # 2차 시도: 가게명만
        logger.warning(f"✗ 1차 검색 실패")
        result = await self.crawl(store_name, output_file, category=category)
        
        if result:
            return result
        
        await asyncio.sleep(4)
        # 3차 시도: 상세주소만
        logger.warning(f"✗ 2차 검색 실패")
        result = await self.crawl(store_address, output_file, category=category)
        
        if result:
            return result
        
        # 4차 시도: 상세주소 + 가게명
        logger.warning(f"✗ 3차 검색 실패")
        fourth_keyword = f"{store_address} {store_name}"
        result = await self.crawl(fourth_keyword, output_file, category=category)
        
        if result:
            return result
        
        logger.error(f"✗ 모든 검색 시도 실패: {store_name}")
        return None
    
    def _extract_search_address(self, address_parts: List[str]) -> str:
        """
        주소에서 검색에 적합한 부분 추출
        - 지번 주소: 시/도 + 시/군/구 + 읍/면/동까지만 (우선)
        - 도로명 주소: 시/도 + 시/군/구 + 도로명까지
        """
        if not address_parts:
            return ""
        
        result_parts = []
        
        for part in address_parts:
            result_parts.append(part)
            
            # ✅ 읍/면/동이 나오면 바로 종료 (지번 주소 우선)
            if part.endswith('읍') or part.endswith('면') or part.endswith('동') or part.endswith('리'):
                break
            
            # 도로명(~로, ~길)이 나오면 종료
            elif part.endswith('로') or part.endswith('길'):
                break
            
            # 안전장치: 최대 4개 요소까지
            if len(result_parts) >= 4:
                break
        
        return " ".join(result_parts)
    
    async def crawl_from_gangnam_api(self, delay: int = 20, output_file: str = None):
        """
        강남구 API에서 데이터를 가져와 크롤링 (DB 저장 없음, 메모리에서만 사용)
        
        Args:
            delay: 크롤링 간 딜레이 (초)
            output_file: JSON 저장 파일 (선택)
        """
        # 강남구 API에서 데이터 가져오기
        api_service = GangnamAPIService()
        api_data = api_service.fetch_all_restaurants()
        
        if not api_data:
            logger.warning("강남구 API에서 데이터를 가져올 수 없습니다.")
            return
        
        # 크롤링용 포맷으로 변환
        stores = api_service.convert_to_store_format(api_data)
        
        total = len(stores)
        success_count = 0
        fail_count = 0
        
        logger.info(f"총 {total}개 강남구 모범음식점 크롤링 시작")
        
        for idx, store in enumerate(stores, 1):
            store_id = store['id']
            store_name = store['name']
            store_address = store['address']  # 지번 주소
            store_type = store['type']
            admdng_nm = store['admdng_nm']
            
            logger.info(f"[{idx}/{total}] ID {store_id}: '{store_name}' (행정동: {admdng_nm}) 크롤링 진행 중...")
            
            # 여러 키워드 조합으로 크롤링 시도
            store_info = await self.crawl_with_fallback(
                store_name, 
                store_address, 
                output_file, 
                category=store_type
            )
            
            if store_info:
                # 주소를 좌표로 변환
                longitude, latitude = self.geocoding_service.get_coordinates(store_info.address)
                
                # ✅ 결과를 메모리에 저장 또는 출력
                success_count += 1
                
                integrated_tags_count = len(store_info.blog_review_tags) if store_info.blog_review_tags else 0
                integrated_tags_str = ", ".join(store_info.blog_review_tags) if store_info.blog_review_tags else "없음"
                
                logger.info(f"✓ [{idx}/{total}] ID {store_id} '{store_name}' 완료")
                logger.info(f"  - 통합 태그: {integrated_tags_count}개 [{integrated_tags_str}]")
                
                if longitude and latitude:
                    logger.info(f"  - 좌표: ({longitude}, {latitude})")
                
                # ✅ 원하는 경우 여기서 DB에 저장하거나 다른 처리 수행 가능
                # 예: db_manager.update_store(store_id, store_info, longitude, latitude)
                
            else:
                fail_count += 1
                logger.error(f"✗ [{idx}/{total}] ID {store_id} '{store_name}' 크롤링 실패")
            
            # 마지막 상점이 아니면 딜레이
            if idx < total:
                await asyncio.sleep(delay)
        
        logger.info(f"=" * 60)
        logger.info(f"크롤링 완료: 성공 {success_count}/{total}, 실패 {fail_count}/{total}")
        logger.info(f"=" * 60)
        
        return success_count
    
    async def _navigate_to_naver_map(self, page):
        """네이버 지도 페이지로 이동"""
        await page.goto(self.naver_map_url)
    
    async def _search_keyword(self, page, keyword: str):
        """키워드 검색"""
        search_input_selector = '.input_search'
        await page.wait_for_selector(search_input_selector)
        await asyncio.sleep(1)
        
        await page.fill(search_input_selector, '')
        await asyncio.sleep(0.5)
        
        await page.fill(search_input_selector, keyword)
        await page.press(search_input_selector, 'Enter')
    
    async def _get_entry_frame(self, page):
        """상세 정보 iframe 가져오기"""
        try:
            await page.wait_for_selector('iframe#entryIframe', timeout=10000)
            entry_frame = page.frame_locator('iframe#entryIframe')
            await asyncio.sleep(3)
            return entry_frame
        except TimeoutError:
            logger.error("entryIframe을 찾을 수 없습니다.")
            return None
    
    async def _extract_store_details(self, entry_frame, original_name: str, page: Page, category: int = 0) -> Optional[StoreInfo]:
        """상점 상세 정보 추출"""
        extractor = StoreDetailExtractor(entry_frame, page)
        return await extractor.extract_all_details(original_name, category=category)
    
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
        """상점 식별을 위한 키 생성"""
        title = title or 'Unknown'
        address = address or ''
        return f"{title}||{address}"
    
    def _save_single_store(self, output_file: str, new_store: StoreInfo):
        """단일 상점 정보를 파일에 추가/업데이트"""
        existing_data = self._load_existing_data(output_file)
        
        existing_dict = {}
        for item in existing_data:
            key = self._create_store_key(item.get('title', ''), item.get('address', ''))
            existing_dict[key] = item
        
        new_item = self._convert_empty_to_null(new_store.model_dump())
        key = self._create_store_key(new_item.get('title') or '', new_item.get('address') or '')
        existing_dict[key] = new_item
        
        all_data = list(existing_dict.values())
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4, default=str)
    
    def _convert_empty_to_null(self, data):
        """빈 값을 null로 변환"""
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
    
    async def extract_all_details(self, original_name: str, category: int = 0) -> Optional[StoreInfo]:
        """모든 상세 정보 추출 및 통합 태그 생성"""
        
        try:
            # 기본 정보 추출
            title = await self._extract_title(original_name)
            address = await self._extract_address()
            phone = await self._extract_phone()
            phone = phone.replace('-','')
            business_hours = await self._extract_business_hours()
            image = await self._extract_image()
            
            # 리뷰 정보 추출
            opinion_data, content_data = await self._extract_reviews()
            
            # 블로그 리뷰 내용 수집
            category_names = {0: "음식점", 1: "카페", 2: "콘텐츠"}
            
            scraper = NaverBlogReviewScraper(self.page, self.frame, category=category)
            blog_review_contents = await scraper.scrape_blog_review_contents()
            
            logger.info(f"블로그 리뷰 수집 완료: {len(blog_review_contents)}개")
            
            # 모든 리뷰 데이터를 통합하여 최종 태그 생성
            try:
                from service.crawl.review_to_tags import ReviewTagClassifier
                tag_classifier = ReviewTagClassifier(category=category, max_tags_per_store=10)
                
                final_tags = tag_classifier.consolidate_all_review_data(
                    naver_opinion_tags=opinion_data,
                    naver_review_contents=content_data,
                    blog_review_contents=blog_review_contents
                )
                
            except Exception as e:
                logger.error(f"통합 태그 생성 실패: {e}")
                final_tags = []
            
            return StoreInfo(
                title=title or "",
                address=address or "",
                phone=phone or "",
                business_hours=business_hours or "",
                image=image or "",
                opinion=[],
                content=[],
                blog_review_tags=final_tags,
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
                    logger.info(f"원본 영업시간 추출: {raw_hours}")
                    
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
        """LLM을 사용하여 영업시간 데이터를 정리"""
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
                response = requests.post(
                    self.api_endpoint,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    cleaned_hours = result['choices'][0]['message']['content'].strip()
                    return cleaned_hours
                else:
                    if response.status_code != 403:
                        logger.warning(f"✗ 영업시간 정리 API 호출 실패 ({attempt}번째 시도) - 상태 코드: {response.status_code}")
                    
                    if attempt < max_retries:
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"✗ 최대 재시도 횟수({max_retries}회) 초과 - 원본 반환")
                        return raw_hours
                
            except requests.exceptions.Timeout:
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
            await self.frame.locator('a[href*="review"][role="tab"]').click()
            await asyncio.sleep(2)
            
            await self._click_review_show_more_buttons()
            
            opinion_data = await self._extract_review_tags()
            content_data = await self._extract_detailed_reviews()
            
        except Exception as e:
            logger.error(f"리뷰 탭 클릭 또는 추출 중 오류: {e}")
        
        return opinion_data, content_data
    
    async def _click_review_show_more_buttons(self):
        """리뷰 더보기 버튼들 클릭"""
        while True:
            try:
                show_more_button = self.frame.locator('div.mrSZf > div > a')
                await show_more_button.click(timeout=3000)
                await asyncio.sleep(1)
            except TimeoutError:
                break
        
        click_count = 0
        while True:
            try:
                show_more_button = self.frame.locator('div.NSTUp > div > a')
                await show_more_button.click(timeout=3000)
                await asyncio.sleep(1)
                click_count += 1
                if click_count == 5:
                    break
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
                    more_button_locator = review_element.locator('div.pui__vn15t2 > a').first
                    
                    if await more_button_locator.is_visible():
                        await more_button_locator.click(timeout=3000)
                        await asyncio.sleep(1)
                    
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
    """메인 함수 - 강남구 API 데이터로 크롤링"""
    
    # ✅ 강남구 API 데이터를 변수에서 꺼내서 사용
    crawler = NaverMapSingleCrawler(headless=False)
    
    # output_file='gangnam_results.json'으로 설정하면 JSON 파일에도 저장
    await crawler.crawl_from_gangnam_api(delay=30, output_file='gangnam_results.json')

if __name__ == "__main__":
    asyncio.run(main())