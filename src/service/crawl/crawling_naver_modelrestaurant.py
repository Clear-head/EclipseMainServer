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
logger = get_logger('crawling_naver_gangnam')


class GangnamAPIService:
    """강남구 모범음식점 API 서비스"""
    
    def __init__(self):
        self.base_url = f'http://openAPI.gangnam.go.kr:8088/{os.getenv("SEOUL_DATA_KEY")}/json/GnModelRestaurantDesignate'
    
    async def fetch_all_restaurants(self) -> List[dict]:
        """
        강남구 모범음식점 API에서 모든 데이터 가져오기 (비동기)
        
        Returns:
            List[dict]: 음식점 데이터 리스트
        """
        try:
            # 전체 개수 확인
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f'{self.base_url}/1/1/') as response:
                    if response.status != 200:
                        logger.error(f"API 호출 오류: {response.status}")
                        return []
                    
                    data = await response.json()
                    total_count = data['GnModelRestaurantDesignate']['list_total_count']
                    logger.info(f"강남구 모범음식점 전체 개수: {total_count}개")
                
                # 모든 데이터 수집
                all_data = []
                batch_size = 1000
                
                tasks = []
                for start in range(1, total_count + 1, batch_size):
                    end = min(start + batch_size - 1, total_count)
                    url = f'{self.base_url}/{start}/{end}/'
                    tasks.append(self._fetch_batch(session, url, start, end))
                
                # 병렬로 데이터 수집
                batch_results = await asyncio.gather(*tasks)
                
                for batch_data in batch_results:
                    if batch_data:
                        all_data.extend(batch_data)
                
                logger.info(f"총 {len(all_data)}개 데이터 수집 완료")
                return all_data
            
        except Exception as e:
            logger.error(f"강남구 API 데이터 수집 중 오류: {e}")
            return []
    
    async def _fetch_batch(self, session, url: str, start: int, end: int) -> List[dict]:
        """배치 데이터 가져오기"""
        try:
            logger.info(f"API 데이터 수집 중... {start}~{end}")
            async with session.get(url) as response:
                if response.status == 200:
                    batch_data = await response.json()
                    if 'GnModelRestaurantDesignate' in batch_data and 'row' in batch_data['GnModelRestaurantDesignate']:
                        return batch_data['GnModelRestaurantDesignate']['row']
                else:
                    logger.error(f"배치 {start}~{end} API 호출 오류: {response.status}")
            return []
        except Exception as e:
            logger.error(f"배치 {start}~{end} 수집 중 오류: {e}")
            return []
    
    def convert_to_store_format(self, api_data: List[dict]) -> List[dict]:
        """
        API 데이터를 크롤링용 포맷으로 변환
        
        Args:
            api_data: API에서 가져온 원본 데이터
            
        Returns:
            List[dict]: 변환된 상점 데이터
        """
        converted_data = []
        
        for idx, row in enumerate(api_data, 1):
            store = {
                'id': idx,
                'name': row.get('UPSO_NM', '').strip(),
                'address': row.get('SITE_ADDR', '').strip(),  # 지번 주소
                'sub_category': row.get('SNT_UPTAE_NM', '').strip(),
                'admdng_nm': row.get('ADMDNG_NM', '').strip(),
                'main_edf': row.get('MAIN_EDF', '').strip(),
                'original_data': row
            }
            converted_data.append(store)
        
        return converted_data


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
            sub_category: 서브 카테고리
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
                                longitude = str(doc['x'])  # 경도 (문자열)
                                latitude = str(doc['y'])   # 위도 (문자열)
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
            
            # 도 단위 매핑 (약칭 처리)
            do_mapping = {
                '경기': '경기도',
                '강원': '강원도',
                '충북': '충청북도',
                '충남': '충청남도',
                '전북': '전북특별자치도',
                '전남': '전라남도',
                '경북': '경상북도',
                '경남': '경상남도',
                '제주': '제주특별자치도'
            }
            
            remaining = full_address
            
            # 1단계: 특별시/광역시/도 처리
            for short_name, full_name in city_mapping.items():
                # "서울" 또는 "서울특별시"로 시작하는 경우
                if remaining.startswith(short_name):
                    si = full_name
                    # "서울" 다음이 공백이거나 구로 끝나는 단어가 오는 경우
                    if len(remaining) > len(short_name):
                        next_char = remaining[len(short_name)]
                        if next_char == ' ':
                            remaining = remaining[len(short_name):].strip()
                        elif next_char in ['구', '군', '시']:
                            remaining = remaining[len(short_name):]
                        else:
                            # "서울특별시"처럼 붙어있는 경우
                            if remaining.startswith(full_name):
                                remaining = remaining[len(full_name):].strip()
                            else:
                                remaining = remaining[len(short_name):]
                    else:
                        remaining = ""
                    break
            
            # 도 단위 처리 (si가 아직 설정되지 않은 경우)
            if not si:
                for short_name, full_name in do_mapping.items():
                    # "경기" 또는 "경기도"로 시작하는 경우
                    if remaining.startswith(short_name):
                        do = full_name
                        # "경기" 다음이 공백이거나 시/군으로 끝나는 단어가 오는 경우
                        if len(remaining) > len(short_name):
                            next_char = remaining[len(short_name)]
                            if next_char == ' ':
                                remaining = remaining[len(short_name):].strip()
                            elif next_char in ['시', '군']:
                                remaining = remaining[len(short_name):]
                            else:
                                # "경기도"처럼 붙어있는 경우
                                if remaining.startswith(full_name):
                                    remaining = remaining[len(full_name):].strip()
                                else:
                                    remaining = remaining[len(short_name):]
                        else:
                            remaining = ""
                        break
                
                # 기존 로직: "경기도", "충청북도" 등 전체 이름으로 끝나는 경우
                if not do:
                    parts = remaining.split(maxsplit=1)
                    if parts:
                        first_word = parts[0]
                        if first_word.endswith('도') or first_word.endswith('특별자치도'):
                            do = first_word
                            remaining = parts[1] if len(parts) > 1 else ""
            
            # 2단계: do가 있는 경우 si 추출 (시/군)
            if do and not si:
                # 공백으로 구분된 경우
                parts = remaining.split(maxsplit=1)
                if parts:
                    first_part = parts[0]
                    if first_part.endswith('시') or first_part.endswith('군'):
                        si = first_part
                        remaining = parts[1] if len(parts) > 1 else ""
                    else:
                        # 공백 없이 붙어있는 경우 (예: "수원시권선구")
                        # 시/군을 찾아서 분리
                        import re
                        match = re.match(r'^([가-힣]+[시군])', remaining)
                        if match:
                            si = match.group(1)
                            remaining = remaining[len(si):].strip()
            
            # 3단계: 구/읍/면 추출
            if remaining:
                # 공백으로 구분된 경우
                parts = remaining.split(maxsplit=1)
                if parts:
                    first_part = parts[0]
                    if first_part.endswith('구') or first_part.endswith('읍') or first_part.endswith('면'):
                        gu = first_part
                        detail_address = parts[1] if len(parts) > 1 else ""
                    else:
                        # 공백 없이 붙어있는 경우 (예: "권선구곡반정동")
                        import re
                        match = re.match(r'^([가-힣]+[구읍면])', remaining)
                        if match:
                            gu = match.group(1)
                            detail_address = remaining[len(gu):].strip()
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


class NaverMapGangnamCrawler:
    """강남구 API 데이터 크롤링 클래스"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.naver_map_url = "https://map.naver.com/v5/search"
        self.geocoding_service = GeocodingService()
        self.category_classifier = CategoryTypeClassifier()
    
    async def _save_store_data(self, idx: int, total: int, store_data: Tuple, store_name: str, store_id: int, api_sub_category: str):
        """
        크롤링한 데이터를 DB에 저장하는 비동기 함수
        
        Args:
            idx: 현재 인덱스
            total: 전체 개수
            store_data: 크롤링한 상점 데이터
            store_name: 상점명
            store_id: 상점 ID
            api_sub_category: API에서 가져온 서브 카테고리 (보조용)
            
        Returns:
            Tuple[bool, str]: (성공 여부, 로그 메시지)
        """
        try:
            name, full_address, phone, business_hours, image, naver_sub_category, tag_reviews = store_data
            
            # 주소 파싱
            do, si, gu, detail_address = AddressParser.parse_address(full_address)
            
            # ⭐ 서브 카테고리 결정: 네이버 지도 우선
            # 1순위: 네이버 지도 서브 카테고리
            # 2순위: API 서브 카테고리
            final_sub_category = naver_sub_category or api_sub_category
            
            logger.info(f"[저장 {idx+1}/{total}] 서브 카테고리 결정:")
            logger.info(f"  - 네이버 서브 카테고리: {naver_sub_category}")
            logger.info(f"  - API 서브 카테고리: {api_sub_category}")
            logger.info(f"  - 최종 선택 (저장 & 타입 분류): {final_sub_category}")
            
            # 좌표 변환과 카테고리 분류를 병렬로 실행
            # ⭐ 네이버 지도의 서브 카테고리로 타입 분류
            (longitude, latitude), category_type = await asyncio.gather(
                self.geocoding_service.get_coordinates(full_address),
                self.category_classifier.classify_category_type(final_sub_category)
            )
            
            # DTO 생성
            category_dto = InsertCategoryDto(
                name=name,
                do=do,
                si=si,
                gu=gu,
                detail_address=detail_address,
                sub_category=final_sub_category,  # 네이버 우선
                business_hour=business_hours or "",
                phone=phone.replace('-', '') if phone else "",
                type=category_type,  # 네이버 서브 카테고리로 분류된 타입
                image=image or "",
                latitude=latitude or "",
                longitude=longitude or ""
            )
            
            # category 저장 (중복 체크 포함)
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
                # 태그 리뷰 저장 (중복 체크 포함)
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
                    f"✓ [저장 {idx+1}/{total}] ID {store_id} '{name}' 완료\n"
                    f"  - 저장된 서브 카테고리: {final_sub_category}\n"
                    f"  - 타입: {type_names.get(category_type, '기타')} ({category_type})\n"
                    f"  - 태그 리뷰: {tag_success_count}/{len(tag_reviews)}개 저장"
                )
                logger.info(success_msg)
                return True, success_msg
            else:
                error_msg = f"✗ [저장 {idx+1}/{total}] ID {store_id} '{name}' DB 저장 실패"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as db_error:
            error_msg = f"✗ [저장 {idx+1}/{total}] ID {store_id} '{store_name}' DB 저장 중 오류: {db_error}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            return False, error_msg
    
    async def crawl_gangnam_api(self, delay: int = 20):
        """
        강남구 API에서 데이터를 가져와 크롤링
        크롤링과 저장을 분리하여 병렬 처리
        
        Args:
            delay: 크롤링 간 딜레이 (초)
        """
        # 강남구 API에서 데이터 가져오기 (비동기)
        api_service = GangnamAPIService()
        api_data = await api_service.fetch_all_restaurants()
        
        if not api_data:
            logger.warning("강남구 API에서 데이터를 가져올 수 없습니다.")
            return
        
        # 크롤링용 포맷으로 변환
        stores = api_service.convert_to_store_format(api_data)
        
        total = len(stores)
        success_count = 0
        fail_count = 0
        
        logger.info(f"총 {total}개 강남구 모범음식점 크롤링 시작")
        logger.info("=" * 60)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--enable-features=ClipboardAPI']  # 클립보드 API 활성화
            )
            
            # 컨텍스트 생성 시 클립보드 권한 부여
            context = await browser.new_context(
                permissions=['clipboard-read', 'clipboard-write']
            )
            page = await context.new_page()
            
            try:
                # 저장 태스크를 담을 리스트
                save_tasks = []
                
                for idx, store in enumerate(stores, 1):
                    store_id = store['id']
                    store_name = store['name']
                    store_address = store['address']  # 지번 주소
                    api_sub_category = store['sub_category']  # API 서브 카테고리
                    admdng_nm = store['admdng_nm']
                    
                    logger.info(f"[크롤링 {idx}/{total}] ID {store_id}: '{store_name}' (행정동: {admdng_nm}) 크롤링 진행 중...")
                    logger.info(f"  - API 서브 카테고리: {api_sub_category}")
                    
                    # 네이버 지도에서 검색
                    store_data = await self._search_and_extract(page, store_name, store_address)
                    
                    if store_data:
                        # store_data에서 네이버 서브 카테고리 추출
                        naver_sub_category = store_data[5]  # (name, address, phone, hours, image, sub_category, tags)
                        logger.info(f"  - 네이버 서브 카테고리: {naver_sub_category}")
                        logger.info(f"✓ [크롤링 {idx}/{total}] ID {store_id} '{store_name}' 크롤링 완료")
                        
                        # 저장 태스크 생성 (백그라운드에서 실행)
                        save_task = asyncio.create_task(
                            self._save_store_data(idx, total, store_data, store_name, store_id, api_sub_category)
                        )
                        save_tasks.append(save_task)
                        
                        # 마지막 상점이 아니면 딜레이
                        if idx < total:
                            logger.info(f"[대기] {delay}초 대기 중... (저장은 백그라운드에서 진행)")
                            await asyncio.sleep(delay)
                    else:
                        fail_count += 1
                        logger.error(f"✗ [크롤링 {idx}/{total}] ID {store_id} '{store_name}' 크롤링 실패")
                        
                        # 실패해도 딜레이
                        if idx < total:
                            logger.info(f"[대기] {delay}초 대기 중...")
                            await asyncio.sleep(delay)
                
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
                logger.error(f"크롤링 중 오류: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                await context.close()
                await browser.close()
    
    async def _search_and_extract(self, page: Page, store_name: str, store_address: str):
        """네이버 지도에서 검색 및 정보 추출"""
        address_parts = store_address.split()
        
        # 1차 시도: 지번주소(~동까지) + 가게명
        if len(address_parts) >= 3:
            first_keyword = f"{self._extract_search_address(address_parts)} {store_name}"
        else:
            first_keyword = f"{store_address} {store_name}"
        
        result = await self._search_single(page, first_keyword)
        if result:
            return result
        
        await asyncio.sleep(4)
        logger.warning(f"✗ 1차 검색 실패")
        result = await self._search_single(page, store_name)
        if result:
            return result
        
        await asyncio.sleep(4)
        logger.warning(f"✗ 2차 검색 실패")
        result = await self._search_single(page, store_address)
        if result:
            return result
        
        logger.warning(f"✗ 3차 검색 실패")
        fourth_keyword = f"{store_address} {store_name}"
        result = await self._search_single(page, fourth_keyword)
        if result:
            return result
        
        logger.error(f"✗ 모든 검색 시도 실패: {store_name}")
        return None
    
    def _extract_search_address(self, address_parts: List[str]) -> str:
        """주소에서 검색에 적합한 부분 추출 (지번 주소 ~동까지)"""
        if not address_parts:
            return ""
        
        result_parts = []
        
        for part in address_parts:
            result_parts.append(part)
            
            # 읍/면/동이 나오면 바로 종료
            if part.endswith('읍') or part.endswith('면') or part.endswith('동') or part.endswith('리'):
                break
            
            # 도로명(~로, ~길)이 나오면 종료
            elif part.endswith('로') or part.endswith('길'):
                break
            
            # 안전장치: 최대 4개 요소까지
            if len(result_parts) >= 4:
                break
        
        return " ".join(result_parts)
    
    async def _search_single(self, page: Page, keyword: str):
        """단일 키워드로 검색"""
        try:
            # 네이버 지도 이동
            await page.goto(self.naver_map_url)
            
            # 검색
            search_input_selector = '.input_search'
            await page.wait_for_selector(search_input_selector)
            await asyncio.sleep(1)
            
            await page.fill(search_input_selector, '')
            await asyncio.sleep(0.5)
            
            await page.fill(search_input_selector, keyword)
            await page.press(search_input_selector, 'Enter')
            
            # entry iframe 대기
            await page.wait_for_selector('iframe#entryIframe', timeout=10000)
            entry_frame = page.frame_locator('iframe#entryIframe')
            await asyncio.sleep(3)
            
            # 정보 추출
            extractor = StoreDetailExtractor(entry_frame, page)
            return await extractor.extract_all_details()
            
        except TimeoutError:
            logger.error(f"'{keyword}' 검색 결과를 찾을 수 없습니다.")
            return None
        except Exception as e:
            logger.error(f"'{keyword}' 검색 중 오류: {e}")
            return None


class StoreDetailExtractor:
    """상점 상세 정보 추출 클래스"""
    
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
            return await name_locator.inner_text(timeout=5000)
        except:
            return ""
    
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
            
            # 지번 주소 추출
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
                logger.info(f"전화번호 추출 성공: {phone}")
                return phone
        except TimeoutError:
            logger.warning(f"기본 전화번호 추출 실패 - 대체 방법 시도")
        except Exception as e:
            logger.warning(f"기본 전화번호 추출 오류: {e} - 대체 방법 시도")
        
        # 2차 시도: a.BfF3H 클릭 후 a.place_bluelink에서 클립보드 복사
        try:
            logger.info("a.BfF3H 버튼 찾는 중...")
            bf_button = self.frame.locator('a.BfF3H')
            
            if await bf_button.count() > 0:
                logger.info("a.BfF3H 버튼 클릭 중...")
                await bf_button.first.click(timeout=3000)
                await asyncio.sleep(1)
                
                # a.place_bluelink 클릭하여 클립보드에 복사
                logger.info("a.place_bluelink 버튼 찾는 중...")
                bluelink_button = self.frame.locator('a.place_bluelink')
                
                if await bluelink_button.count() > 0:
                    logger.info("a.place_bluelink 버튼 클릭 중 (클립보드 복사)...")
                    
                    # 클립보드 권한 허용 및 클릭
                    await bluelink_button.first.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    
                    # 클립보드에서 전화번호 가져오기
                    try:
                        # Playwright의 page 객체를 통해 클립보드 접근
                        clipboard_text = await self.page.evaluate('navigator.clipboard.readText()')
                        
                        if clipboard_text and clipboard_text.strip():
                            logger.info(f"클립보드에서 전화번호 추출 성공: {clipboard_text}")
                            return clipboard_text.strip()
                        else:
                            logger.warning("클립보드가 비어있습니다")
                    except Exception as clipboard_error:
                        logger.error(f"클립보드 읽기 실패: {clipboard_error}")
                else:
                    logger.warning("a.place_bluelink 버튼을 찾을 수 없습니다")
            else:
                logger.warning("a.BfF3H 버튼을 찾을 수 없습니다")
                
        except Exception as e:
            logger.error(f"대체 전화번호 추출 중 오류: {e}")
        
        logger.warning("전화번호를 추출할 수 없습니다 - 빈 값 반환")
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
                                await asyncio.sleep(2)
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
                except:
                    continue
            
            logger.info(f"태그 리뷰 {len(tag_reviews)}개 추출 완료")
            
        except Exception as e:
            logger.error(f"태그 리뷰 추출 중 오류: {e}")
        
        return tag_reviews


async def main():
    """메인 함수"""
    
    # 크롤러 생성
    crawler = NaverMapGangnamCrawler(headless=False)
    
    # 강남구 API 데이터로 크롤링 시작
    await crawler.crawl_gangnam_api(delay=30)

if __name__ == "__main__":
    asyncio.run(main())