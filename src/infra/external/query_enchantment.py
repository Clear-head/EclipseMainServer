"""
Copilot API를 사용한 검색 쿼리 개선 및 GPT 기반 추천 필터링 서비스
"""
import asyncio
import os
from typing import Optional, List, Dict

import aiohttp
from dotenv import load_dotenv

from src.logger.custom_logger import get_logger
from src.utils.path import path_dic

load_dotenv(dotenv_path=path_dic["env"])
logger = get_logger(__name__)


class QueryEnhancementService:
    """사용자 입력을 자연스러운 검색 쿼리로 변환하고, GPT-4.1로 추천 결과를 재정렬/필터링"""

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
            logger.warning("GitHub API 토큰이 없습니다. 쿼리 개선 및 GPT 필터링 기능이 비활성화됩니다.")

    async def enhance_query(
        self,
        personnel: Optional[int],
        category_type: Optional[str],
        user_keyword: str,
        max_retries: int = 10
    ) -> str:
        """
        사용자 입력을 자연스러운 검색 문장으로 변환 (Copilot API 호출)
        """
        if not self.api_token:
            return self._build_fallback_query(personnel, category_type, user_keyword)

        if not user_keyword or not user_keyword.strip():
            return self._build_fallback_query(personnel, category_type, user_keyword)

        prompt = self._build_prompt(personnel, category_type, user_keyword)

        payload = {
    "model": "gpt-4.1",
    "messages": [
        {
            "role": "system",
            "content": """당신은 매장 추천 전문가입니다. 
반드시 첫 줄에 "SELECTED: 숫자,숫자,숫자" 또는 "SELECTED: NONE" 형식으로 출력하세요.
설명은 간결하게(2-3줄) 작성하세요.

⚠️ 중요 규칙:
1. 여러 키워드는 OR 조건입니다 (하나라도 일치하면 선택)
2. 메뉴 키워드는 유연하게 해석하세요
   - "딸기라떼" → "딸기" 메뉴만 있어도 선택 (딸기케이크, 딸기빙수 등)
   - "포테이토피자" → "피자" 메뉴만 있어도 선택 (토핑 변경 가능)
   - 정확한 메뉴명이 없어도 관련 재료가 있으면 포함
3. 너무 엄격하게 평가하지 마세요. 가능성이 있으면 포함하세요.
4. 키워드는 메뉴, 분위기, 뷰, 스타일 등 다양한 의미를 가질 수 있습니다."""
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
        max_results: int = 10,
        max_retries: int = 10,
        fill_with_original: bool = False
    ) -> List[Dict]:
        """
        GPT-4.1을 사용하여 추천 결과를 필터링 및 재정렬
        """
        if not self.api_token:
            logger.warning("API 토큰 없음 - 원본 결과 반환")
            return stores[:max_results]

        if not stores:
            logger.warning("필터링할 매장이 없습니다.")
            return []

        logger.info(f"GPT-4.1 필터링 시작: 후보 {len(stores)}개 → 최대 {max_results}개 선택 (fill_with_original={fill_with_original})")
        logger.info(f"키워드: {user_keywords}, 카테고리: {category_type}, 인원: {personnel}")

        stores_summary = []
        for idx, store in enumerate(stores, 1):
            summary = {
                "순번": idx,
                "매장ID": store.get('id', ''),
                "이름": store.get('title', '') or store.get('name', ''),
                "주소": store.get('detail_address', '') or store.get('address', ''),
                "카테고리": store.get('sub_category', '') or store.get('category', ''),
                "메뉴": (store.get('menu') if store.get('menu') else '정보없음')
            }
            stores_summary.append(summary)

        # 카테고리별 필터링 기준 생성
        filtering_criteria = self._get_filtering_criteria(category_type, personnel, user_keywords, max_results)

        prompt = f"""다음은 ChromaDB + 하이브리드 검색으로 추천된 {category_type} 매장 목록입니다.
    사용자의 요구사항에 가장 적합한 매장을 최대 {max_results}개 선택하고, 적합도 순으로 정렬하세요.

    <사용자 요구사항>
    - 카테고리: {category_type}
    - 인원: {personnel}명
    - 키워드: {', '.join(user_keywords)}

    <추천된 매장 목록>
    {self._format_stores_for_prompt(stores_summary)}

    {filtering_criteria}

    <중요 규칙>
    - ⚠️ 적합한 매장이 전혀 없다면 "NONE"을 출력하세요.
    - 카테고리 특성에 맞게 평가하세요.

    <출력 형식 - 매우 중요!>
    ⚠️ 반드시 다음 형식을 정확히 따르세요:

    경우 1) 적합한 매장이 있는 경우:
    SELECTED: 3,7,2,9,1
    (설명은 선택사항)

    경우 2) 적합한 매장이 전혀 없는 경우:
    SELECTED: NONE
    (이유 설명)

    선택된 매장:"""

        payload = {
            "model": "gpt-4.1",
            "messages": [
                {
                    "role": "system",
                    "content": """당신은 매장 추천 전문가입니다. 
    반드시 첫 줄에 "SELECTED: 숫자,숫자,숫자" 또는 "SELECTED: NONE" 형식으로 출력하세요.
    설명은 그 다음 줄부터 작성하세요.
    카테고리에 따라 적절한 기준으로 평가하세요 (콘텐츠는 메뉴보다 활동/분위기 중심)."""
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

                            # NONE 체크
                            if self._is_gpt_none_response(gpt_output):
                                logger.info("GPT가 적합한 매장이 없다고 판단 - 빈 리스트 반환")
                                return []

                            selected_indices = self._parse_gpt_selection(gpt_output, len(stores))
                            if not selected_indices:
                                logger.warning("GPT 파싱 실패 - 빈 리스트 반환")
                                return []

                            filtered_stores = [stores[idx - 1] for idx in selected_indices if 1 <= idx <= len(stores)]

                            # fill_with_original 옵션 처리
                            if fill_with_original and len(filtered_stores) < max_results:
                                added = []
                                for s in stores:
                                    if s not in filtered_stores:
                                        added.append(s)
                                    if len(filtered_stores) + len(added) >= max_results:
                                        break
                                filtered_stores.extend(added[: max_results - len(filtered_stores)])

                            filtered_stores = filtered_stores[:max_results]
                            logger.info(f"GPT 필터링 완료: {len(filtered_stores)}개 매장 선택")
                            logger.info(f"선택된 순번: {selected_indices[:max_results]}")
                            return filtered_stores
                        else:
                            logger.warning(f"GPT 필터링 API 호출 실패 ({attempt}번째 시도) - 상태 코드: {response.status}")
                            if attempt < max_retries:
                                await asyncio.sleep(1)
                            else:
                                logger.warning("최대 재시도 초과 - 빈 리스트 반환")
                                return []
            except asyncio.TimeoutError:
                logger.warning(f"GPT 필터링 API 시간 초과 ({attempt}번째 시도)")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.warning("최대 재시도 초과 - 빈 리스트 반환")
                    return []
            except Exception as e:
                logger.error(f"GPT 필터링 중 오류 ({attempt}번째 시도): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.error("최대 재시도 초과 - 빈 리스트 반환")
                    return []

        return []

    def _get_filtering_criteria(self, category_type: str, personnel: int, user_keywords: List[str], max_results: int) -> str:
        """
        카테고리별로 다른 필터링 기준 생성
        """
        # 콘텐츠 카테고리 (동물카페, 체험, 문화 등)
        content_categories = ['콘텐츠', '체험', '문화', '활동', '레저']
        
        # 키워드 목록 생성
        keywords_str = ', '.join([f'"{kw}"' for kw in user_keywords])
        
        if category_type in content_categories or any(keyword in ['동물', '동물카페', '애견', '고양이', '체험', '미술', '전시'] for keyword in user_keywords):
            return f"""<필터링 기준 (우선순위 순)>
    1. 🔥 [최우선] 매장 이름, 카테고리, 설명에 사용자 키워드({keywords_str}) 중 **하나 이상**과 관련된 내용이 있는지
    - ⚠️ 키워드는 OR 조건입니다! 하나라도 일치하면 선택하세요.
    - 예: "동물카페" → "고양이카페", "애견카페" 등 선택
    - 예: "체험" → "도예 공방", "미술관" 등 선택
    2. 카테고리가 사용자 요구사항과 일치하는지
    3. 매장 이름에서 키워드와의 관련성
    4. 인원({personnel}명)에 적합한 분위기인지
    5. 중복/유사 매장 제외

    ⚠️ 이 카테고리에서는 메뉴 정보가 없어도 괜찮습니다!
    ⚠️ 매장 이름, 카테고리, 분위기를 우선적으로 평가하세요!"""
        
        # 음식점, 카페 등
        else:
            return f"""<필터링 기준 (우선순위 순)>
    1. 🔥 [최우선] 사용자 키워드({keywords_str}) 중 **하나 이상**과 관련된 매장을 선택
    - ⚠️ 키워드는 OR 조건입니다! 하나라도 일치하면 선택하세요.
    - ⚠️ 키워드는 메뉴, 분위기, 뷰, 태그 등 다양한 속성을 의미할 수 있습니다!
    
    **키워드 매칭 방법:**
    
    a) 메뉴 키워드 - 유연한 매칭 적용
        - ⚠️ 정확한 메뉴명이 없어도 관련 재료/요소가 있으면 선택하세요!
        
        예시 1: "딸기라떼" 키워드
        → ✅ 메뉴에 "딸기라떼" 있음 (완전 일치)
        → ✅ 메뉴에 "딸기" + "라떼" 관련 메뉴 둘 다 있음 (높은 관련성)
        → ✅ 메뉴에 "딸기" 관련 메뉴(딸기케이크, 딸기빙수 등) 있음 (중간 관련성)
        → ✅ 카페인데 다양한 라떼 메뉴 있음 (낮은 관련성)
        → ❌ 딸기 관련 메뉴가 전혀 없음
        
        예시 2: "초밥, 육회" 키워드
        → ✅ 초밥집 또는 육회집 모두 선택
        → ✅ "회" 메뉴 있으면 초밥 만들 가능성 있음
        
        예시 3: "포테이토피자" 키워드
        → ✅ "피자" 메뉴 있으면 선택 (토핑 변경 가능)
        → ✅ "감자" 또는 "포테이토" 요리 있으면 추가 점수
    
    b) 분위기/속성 키워드
        → 매장 이름, 카테고리, 주소, 분위기 등에서 관련성 확인
        → 예: "뷰가 좋은" → 루프탑, 강변, 한강뷰 등
        → 예: "데이트" → 분위기 있는, 프라이빗한 매장
        → 예: "혼밥" → 1인 좌석, 바 테이블 있는 매장
    
    c) 스타일 키워드
        → 매장 이름, 카테고리에서 스타일 추론
        → 예: "감성" → 인테리어가 특색있는 카페/레스토랑
    
    2. 키워드와의 관련성이 높을수록 더 높은 점수
    - 완전 일치 > 부분 일치 > 관련 재료/요소 있음
    3. 여러 키워드를 동시에 만족하는 매장에 더 높은 점수
    4. 메뉴의 다양성과 풍부함 (메뉴 키워드인 경우)
    5. 카테고리가 {category_type}에 적합한지
    6. 인원({personnel}명)에 적합한 분위기인지
    7. 중복/유사 매장 제외

    ⚠️ 정확한 메뉴명이 없어도 관련 재료/요소가 있으면 반드시 선택하세요!
    ⚠️ 메뉴 키워드는 유연하게 해석하세요 (예: "딸기라떼" → "딸기" 메뉴 있으면 OK)
    ⚠️ 메뉴 정보만이 아니라 매장의 모든 속성을 종합적으로 평가하세요!
    ⚠️ 너무 엄격하게 평가하지 마세요. 관련성이 조금이라도 있으면 포함하세요!"""

    def _format_stores_for_prompt(self, stores_summary: List[Dict]) -> str:
        """매장 목록을 프롬프트용 텍스트로 변환 (메뉴 정보 강조)"""
        lines = []
        for store in stores_summary:
            menu = store.get('메뉴', '정보없음')
            if menu and menu != '정보없음':
                line = f"{store['순번']}. {store['이름']} | 카테고리: {store['카테고리']} | 메뉴: {menu[:120]} | 주소: {store['주소']}"
            else:
                line = f"{store['순번']}. {store['이름']} | 카테고리: {store['카테고리']} | ⚠️ 메뉴 정보 없음 | 주소: {store['주소']}"
            lines.append(line)
        return "\n".join(lines)

    def _is_gpt_none_response(self, gpt_output: str) -> bool:
        """
        GPT가 적합한 매장이 없다고 판단했는지 확인
        """
        gpt_output_upper = gpt_output.upper()
        
        # "SELECTED: NONE" 패턴 체크
        if "SELECTED:" in gpt_output_upper and "NONE" in gpt_output_upper:
            # SELECTED: 다음에 NONE이 있는지 확인
            import re
            match = re.search(r'SELECTED:\s*NONE', gpt_output, re.IGNORECASE)
            if match:
                return True
        
        return False

    def _parse_gpt_selection(self, gpt_output: str, total_count: int) -> List[int]:
        """
        GPT 응답에서 선택된 순번 파싱 (개선된 버전)
        """
        try:
            import re
            
            # 1. "SELECTED:" 패턴이 있는지 확인
            if "SELECTED:" in gpt_output.upper():
                # SELECTED: 다음의 첫 번째 줄만 추출 (줄바꿈 전까지)
                match = re.search(r'SELECTED:\s*([^\n\r]+)', gpt_output, re.IGNORECASE)
                if match:
                    numbers_line = match.group(1).strip()
                    
                    # "NONE" 체크 (이미 _is_gpt_none_response에서 처리하지만 이중 체크)
                    if "NONE" in numbers_line.upper():
                        logger.info("GPT가 NONE 응답 - 빈 리스트 반환")
                        return []
                    
                    # 콤마로 구분된 숫자만 추출
                    if ',' in numbers_line:
                        # 콤마로 분리
                        parts = numbers_line.split(',')
                        selected = []
                        for part in parts:
                            # 각 부분에서 숫자만 추출 (공백, 괄호 등 제거)
                            nums = re.findall(r'\d+', part)
                            if nums:
                                selected.append(int(nums[0]))  # 첫 번째 숫자만
                    else:
                        # 콤마가 없으면 공백으로 구분된 숫자 추출
                        selected = [int(n) for n in re.findall(r'\b\d+\b', numbers_line)]
                else:
                    logger.warning("SELECTED: 패턴 매칭 실패")
                    selected = []
            else:
                # 2. "SELECTED:" 없으면 첫 줄에서만 숫자 추출
                first_line = gpt_output.split('\n')[0]
                # 괄호 안의 내용 제거 (설명 제거)
                first_line = re.sub(r'\([^)]*\)', '', first_line)
                # 콤마로 구분된 숫자만 추출
                if ',' in first_line:
                    parts = first_line.split(',')
                    selected = []
                    for part in parts:
                        nums = re.findall(r'\d+', part)
                        if nums:
                            selected.append(int(nums[0]))
                else:
                    # 공백으로 구분된 숫자 추출 (첫 줄만)
                    selected = [int(n) for n in re.findall(r'\b\d+\b', first_line)]
            
            # 3. 유효성 검증 및 중복 제거
            valid_selected = [n for n in selected if 1 <= n <= total_count]
            seen = set()
            unique_selected = []
            for n in valid_selected:
                if n not in seen:
                    seen.add(n)
                    unique_selected.append(n)
            
            if not unique_selected:
                logger.warning(f"파싱 실패 - GPT 출력: {gpt_output[:200]}")
            else:
                logger.info(f"파싱 성공 - 선택된 순번: {unique_selected} (총 {len(unique_selected)}개)")
            
            return unique_selected
        except Exception as e:
            logger.error(f"GPT 응답 파싱 실패: {e}\n출력: {gpt_output[:200]}")
            return []

    def _build_prompt(
        self,
        personnel: Optional[int],
        category_type: Optional[str],
        user_keyword: str
    ) -> str:
        """프롬프트 생성 (쿼리 개선용)"""
        context_parts = []
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
        if personnel and personnel == 1:
            query_parts.append("혼자 가기 좋은")
        if user_keyword and user_keyword.strip():
            keywords = user_keyword.strip()
            if "," in keywords:
                items = [k.strip() for k in keywords.split(",")]
                if len(items) == 2:
                    keywords = f"{items[0]}, {items[1]}"
                elif len(items) > 2:
                    keywords = f"{', '.join(items[:-1])}, {items[-1]}"
            query_parts.append(keywords)
        final_query = " ".join(query_parts) if query_parts else "추천"
        return final_query