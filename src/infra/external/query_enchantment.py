"""
Copilot API를 사용한 검색 쿼리 개선 서비스
"""
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from typing import Optional, List, Dict

from src.utils.path import path_dic
from src.logger.custom_logger import get_logger

load_dotenv(dotenv_path=path_dic["env"])
logger = get_logger(__name__)


class QueryEnhancementService:
    """사용자 입력을 자연스러운 검색 쿼리로 변환하는 클래스"""
    
    def __init__(self):
        self.api_token = os.getenv('COPILOT_API_KEY2')
        if self.api_token:
            self.api_endpoint = "https://api.githubcopilot.com/chat/completions"
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            logger.info("Copilot API 쿼리 개선 서비스 초기화 완료")
        else:
            logger.warning("GitHub API 토큰이 없습니다. 쿼리 개선 기능이 비활성화됩니다.")
    
    async def enhance_query(
        self,
        personnel: Optional[int],
        category_type: Optional[str],
        user_keyword: str,
        max_retries: int = 10
    ) -> str:
        """
        사용자 입력을 자연스러운 검색 문장으로 변환
        
        Args:
            personnel: 인원 수
            category_type: 카테고리 타입 (음식점, 카페, 콘텐츠)
            user_keyword: 사용자 입력 키워드
            max_retries: 최대 재시도 횟수
            
        Returns:
            str: 개선된 검색 쿼리
        """
        # API 토큰이 없으면 기본 쿼리 생성
        if not self.api_token:
            return self._build_fallback_query(personnel, category_type, user_keyword)
        
        # 사용자 입력이 비어있으면 기본 쿼리
        if not user_keyword or not user_keyword.strip():
            return self._build_fallback_query(personnel, category_type, user_keyword)
        
        # 프롬프트 구성
        prompt = self._build_prompt(personnel, category_type, user_keyword)
        
        payload = {
            "model": "gpt-4.1",
            "messages": [
                {
                    "role": "system",
                    "content": """당신은 매장 검색을 위한 쿼리 최적화 전문가입니다. 
사용자의 입력을 매장 검색에 최적화된 자연스러운 한국어 문장으로 변환하세요.

중요 규칙:
- 반드시 완전한 문장 형태로 작성 (주어+서술어)
- 단순 키워드 나열 금지
- "~한", "~있는", "~좋은" 등 형용사 형태로 자연스럽게 연결
- 구어체나 띄어쓰기 오류를 수정
- 검색 의도를 명확히 표현
- 한국어로만 답변"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 100
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        self.api_endpoint,
                        headers=self.headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            enhanced_query = result['choices'][0]['message']['content'].strip()
                            
                            # 불필요한 따옴표나 마침표 제거
                            enhanced_query = enhanced_query.strip('"\'.')
                            
                            logger.info(f"쿼리 개선 완료: '{user_keyword}' → '{enhanced_query}'")
                            return enhanced_query
                        else:
                            logger.warning(f"쿼리 개선 API 호출 실패 ({attempt}번째 시도) - 상태 코드: {response.status}")
                            
                            if attempt < max_retries:
                                await asyncio.sleep(0.5)
                            else:
                                logger.warning("최대 재시도 초과 - 기본 쿼리 사용")
                                return self._build_fallback_query(personnel, category_type, user_keyword)
                
            except asyncio.TimeoutError:
                logger.warning(f"쿼리 개선 API 시간 초과 ({attempt}번째 시도)")
                
                if attempt < max_retries:
                    await asyncio.sleep(1)
                else:
                    logger.warning("최대 재시도 초과 - 기본 쿼리 사용")
                    return self._build_fallback_query(personnel, category_type, user_keyword)
                    
            except Exception as e:
                logger.error(f"쿼리 개선 중 오류 ({attempt}번째 시도): {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(1)
                else:
                    logger.error("최대 재시도 초과 - 기본 쿼리 사용")
                    return self._build_fallback_query(personnel, category_type, user_keyword)
        
        return self._build_fallback_query(personnel, category_type, user_keyword)
    
    async def filter_recommendations_with_gpt(
        self,
        stores: List[Dict],
        user_keywords: List[str],
        category_type: str,
        personnel: int,
        max_results: int = 8,
        max_retries: int = 3
    ) -> List[Dict]:
        """
        GPT-4.1을 사용하여 추천 결과를 필터링 및 재정렬
        
        Args:
            stores: 추천된 매장 리스트 (MainScreenCategoryList 형식의 dict)
            user_keywords: 사용자가 입력한 키워드 리스트
            category_type: 카테고리 타입 (음식점, 카페, 콘텐츠)
            personnel: 인원 수
            max_results: 최대 반환 개수 (기본 8개)
            max_retries: 최대 재시도 횟수
            
        Returns:
            List[Dict]: GPT가 필터링한 매장 리스트
        """
        if not self.api_token:
            logger.warning("API 토큰 없음 - 원본 결과 반환")
            return stores[:max_results]
        
        if not stores:
            logger.warning("필터링할 매장이 없습니다.")
            return []
        
        logger.info(f"GPT-4.1 필터링 시작: {len(stores)}개 매장 → 최대 {max_results}개 선택")
        logger.info(f"키워드: {user_keywords}, 카테고리: {category_type}, 인원: {personnel}명")
        
        # 매장 정보 간결하게 정리
        stores_summary = []
        for idx, store in enumerate(stores, 1):
            summary = {
                "순번": idx,
                "매장ID": store.get('id', ''),
                "이름": store.get('title', ''),
                "주소": store.get('detail_address', ''),
                "카테고리": store.get('sub_category', '')
            }
            stores_summary.append(summary)
        
        # 프롬프트 구성
        prompt = f"""다음은 ChromaDB + 하이브리드 검색으로 추천된 {category_type} 매장 목록입니다.
사용자의 요구사항에 가장 적합한 매장을 최대 {max_results}개 선택하고, 적합도 순으로 정렬하세요.

<사용자 요구사항>
- 카테고리: {category_type}
- 인원: {personnel}명
- 키워드: {', '.join(user_keywords)}

<추천된 매장 목록>
{self._format_stores_for_prompt(stores_summary)}

<필터링 기준 (우선순위 순)>
1. 🔥 [최우선] 메뉴에 사용자 키워드가 정확히 포함되는지
   - "김치찌개" 키워드 → 메뉴에 "김치찌개"가 있는 매장 최우선
   - "참치" 키워드 → 메뉴에 "참치"가 있는 매장 최우선
   
2. 메뉴 정보가 있는 매장 > 메뉴 정보가 없는 매장
   - ⚠️ 메뉴 정보 없음: 하위 순위로 배치
   
3. {category_type} 타입에 적합한지
4. 인원({personnel}명)에 적합한 분위기인지
5. 중복/유사 매장 제외

<중요 규칙>
❌ 나쁜 선택: 카테고리만 "찌개,전골"이고 메뉴 정보가 없는 매장
✅ 좋은 선택: 메뉴에 "김치찌개, 된장찌개" 등이 명시된 매장

<출력 형식>
선택된 매장의 순번만 콤마로 구분하여 출력하세요. (예: 6,7,8,1,2)
- 최대 {max_results}개까지만 선택
- 메뉴 정보가 있고 키워드와 정확히 매칭되는 매장을 최우선 선택
- 순번만 출력 (설명 불필요)

선택된 매장 순번:"""

        payload = {
            "model": "gpt-4.1",
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 매장 추천 전문가입니다. 사용자의 요구사항에 가장 적합한 매장을 선택하고 정렬하세요."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "max_tokens": 200
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=15)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        self.api_endpoint,
                        headers=self.headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            gpt_output = result['choices'][0]['message']['content'].strip()
                            
                            logger.info(f"GPT 응답: {gpt_output}")
                            
                            # 순번 파싱 (예: "1,3,5,7,2,4,8")
                            selected_indices = self._parse_gpt_selection(gpt_output, len(stores))
                            
                            if not selected_indices:
                                logger.warning("GPT 파싱 실패 - 원본 결과 반환")
                                return stores[:max_results]
                            
                            # 선택된 순번대로 매장 재정렬
                            filtered_stores = [stores[idx - 1] for idx in selected_indices if 1 <= idx <= len(stores)]
                            filtered_stores = filtered_stores[:max_results]
                            
                            logger.info(f"GPT 필터링 완료: {len(filtered_stores)}개 매장 선택")
                            logger.info(f"선택된 순번: {selected_indices[:max_results]}")
                            
                            return filtered_stores
                        else:
                            logger.warning(f"GPT 필터링 API 호출 실패 ({attempt}번째 시도) - 상태 코드: {response.status}")
                            
                            if attempt < max_retries:
                                await asyncio.sleep(1)
                            else:
                                logger.warning("최대 재시도 초과 - 원본 결과 반환")
                                return stores[:max_results]
                
            except asyncio.TimeoutError:
                logger.warning(f"GPT 필터링 API 시간 초과 ({attempt}번째 시도)")
                
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.warning("최대 재시도 초과 - 원본 결과 반환")
                    return stores[:max_results]
                    
            except Exception as e:
                logger.error(f"GPT 필터링 중 오류 ({attempt}번째 시도): {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.error("최대 재시도 초과 - 원본 결과 반환")
                    return stores[:max_results]
        
        return stores[:max_results]
    
    def _format_stores_for_prompt(self, stores_summary: List[Dict]) -> str:
        """매장 목록을 프롬프트용 텍스트로 변환 (메뉴 정보 강조)"""
        lines = []
        for store in stores_summary:
            menu = store.get('menu', '')
            if menu and menu != '정보없음':
                line = f"{store['순번']}. {store['이름']} | 카테고리: {store['카테고리']} | 메뉴: {menu[:100]} | 주소: {store['주소']}"
            else:
                line = f"{store['순번']}. {store['이름']} | 카테고리: {store['카테고리']} | ⚠️ 메뉴 정보 없음 | 주소: {store['주소']}"
            lines.append(line)
        return "\n".join(lines)
    
    def _parse_gpt_selection(self, gpt_output: str, total_count: int) -> List[int]:
        """
        GPT 응답에서 선택된 순번 파싱
        
        Args:
            gpt_output: GPT 응답 텍스트 (예: "1,3,5,7,2,4,8")
            total_count: 전체 매장 개수
            
        Returns:
            List[int]: 선택된 순번 리스트
        """
        try:
            # 숫자와 콤마만 추출
            import re
            numbers_str = re.findall(r'\d+', gpt_output)
            
            # 정수 변환
            selected = [int(n) for n in numbers_str if n.isdigit()]
            
            # 유효한 범위만 필터링 (1 ~ total_count)
            valid_selected = [n for n in selected if 1 <= n <= total_count]
            
            # 중복 제거 (순서 유지)
            seen = set()
            unique_selected = []
            for n in valid_selected:
                if n not in seen:
                    seen.add(n)
                    unique_selected.append(n)
            
            return unique_selected
            
        except Exception as e:
            logger.error(f"GPT 응답 파싱 실패: {e}")
            return []
    
    def _build_prompt(
        self,
        personnel: Optional[int],
        category_type: Optional[str],
        user_keyword: str
    ) -> str:
        """프롬프트 생성"""
        context_parts = []
        
        # 1명일 때만 인원수 언급
        if personnel and personnel == 1:
            context_parts.append("혼자 방문")
        
        if category_type:
            context_parts.append(f"타입: {category_type}")
        
        context = ", ".join(context_parts) if context_parts else "제약 없음"
        
        prompt = f"""다음 사용자 입력을 매장 검색에 최적화된 자연스러운 한국어 문장으로 변환하세요.

<사용자 입력>
{user_keyword}

<상황 정보>
{context}

<변환 규칙>
1. 반드시 완전한 문장 형태로 작성 (키워드 나열 금지)
2. 1명일 때만 "혼자", "혼밥" 키워드 포함
3. 2명 이상일 때는 인원수 언급 안 함
4. 형용사 형태로 자연스럽게 연결
5. 검색 의도를 명확히 표현

<변환 예시>
입력: "조용하고 분위기좋은곳" (1명)
출력: 혼자 있기 좋은 조용하고 분위기 좋은 곳

입력: "조용하고 분위기좋은곳" (2명 이상)
출력: 조용하고 분위기 좋은 곳

입력: "혼밥하기좋고 맛있는곳" (1명)
출력: 혼자 식사하기 좋고 음식이 맛있는 곳

입력: "데이트하기딱좋음" (2명)
출력: 데이트하기 좋은 분위기의 곳

입력: "삼겹살, 저렴한, 된장찌개" (2명 이상, 음식점)
출력: 저렴한 가격에 삼겹살과 된장찌개를 먹을 수 있는 곳

입력: "쑥라떼, 에끌레어" (2명 이상, 카페)
출력: 쑥라떼와 에끌레어가 있는 카페

입력: "커피맛있고 조용한" (2명 이상, 카페)
출력: 커피가 맛있고 조용한 카페

❌ 나쁜 예시: "저렴한 삼겹살 된장찌개" (키워드 나열)
✅ 좋은 예시: "저렴한 가격에 삼겹살과 된장찌개를 먹을 수 있는 곳" (완전한 문장)

변환된 검색 문장 (완전한 문장 형태로, 한국어로만):"""
        
        return prompt
    
    def _build_fallback_query(
        self,
        personnel: Optional[int],
        category_type: Optional[str],
        user_keyword: str
    ) -> str:
        """API 실패 시 기본 쿼리 생성"""
        query_parts = []
        
        # 1명일 때만 인원수 키워드 추가
        if personnel and personnel == 1:
            query_parts.append("혼자 가기 좋은")
        
        # 사용자 키워드
        if user_keyword and user_keyword.strip():
            # 키워드 정리
            keywords = user_keyword.strip()
            
            # 쉼표로 구분된 경우 자연스럽게 연결
            if "," in keywords:
                items = [k.strip() for k in keywords.split(",")]
                if len(items) == 2:
                    keywords = f"{items[0]}, {items[1]}"
                elif len(items) > 2:
                    keywords = f"{', '.join(items[:-1])}, {items[-1]}"
            
            query_parts.append(keywords)
        
        final_query = " ".join(query_parts) if query_parts else "추천"
        
        return final_query