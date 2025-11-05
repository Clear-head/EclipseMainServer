"""
Copilot API를 사용한 검색 쿼리 개선 및 GPT 기반 추천 필터링 서비스
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

        Args:
            stores: 추천된 매장 리스트 (각 항목은 dict; menu, sub_category, detail_address 가능)
            user_keywords: 사용자가 입력한 키워드 리스트
            category_type: 카테고리 타입 (음식점, 카페 등)
            personnel: 인원 수
            max_results: 최대 반환 개수
            max_retries: API 재시도 횟수
            fill_with_original: True이면 GPT가 선택한 개수보다 부족하면 원본에서 채움.
                                False이면 GPT가 선택한 개수만 반환.
        Returns:
            List[Dict]: GPT가 필터링한 매장 리스트
        """
        if not self.api_token:
            logger.warning("API 토큰 없음 - 원본 결과 반환")
            return stores[:max_results]

        if not stores:
            logger.warning("필터링할 매장이 없습니다.")
            return []

        logger.info(f"GPT-4.1 필터링 시작: 후보 {len(stores)}개 → 최대 {max_results}개 선택 (fill_with_original={fill_with_original})")
        logger.info(f"키워드: {user_keywords}, 카테고리: {category_type}, 인원: {personnel}")

        # 요약/프롬프트 준비 (메뉴 정보 강조)
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

        prompt = f"""다음은 ChromaDB + 하이브리드 검색으로 추천된 {category_type} 매장 목록입니다.
사용자의 요구사항에 가장 적합한 매장을 최대 {max_results}개 선택하고, 적합도 순으로 정렬하세요.

<사용자 요구사항>
- 카테고리: {category_type}
- 인원: {personnel}명
- 키워드: {', '.join(user_keywords)}

<추천된 매장 목록>
{self._format_stores_for_prompt(stores_summary)}

<필터링 기준 (우선순위 순)>
1. 🔥 [최우선] 메뉴에 사용자 키워드와 관련된 항목이 있는지
   - 예: "포테이토피자" 키워드 → 메뉴에 "피자" 관련 항목이 있는 매장 선택
   - 완전 일치가 아니어도 관련성이 있으면 높은 점수
   - 메뉴 카테고리가 키워드와 일치하면 우선 선택
2. 메뉴의 다양성과 풍부함
3. 키워드와 유사한 메뉴가 많을수록 높은 점수
4. 카테고리가 {category_type}에 적합한지 (2차적 고려)
5. 인원({personnel}명)에 적합한 분위기인지
6. 중복/유사 매장 제외

<중요 규칙>
- ⚠️ 메뉴 매칭을 최우선으로 평가하세요.
- 메뉴에 키워드가 포함되면 카테고리가 다소 다르더라도 우선 선택
- 메뉴 정보가 없는 매장은 가능한 제외
- 출력은 순번(숫자)만 콤마로 구분해서 주세요.

<출력 형식>
선택된 매장의 순번만 콤마로 구분하여 출력하세요. (예: 1,3,5,7,2)

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

                            selected_indices = self._parse_gpt_selection(gpt_output, len(stores))
                            if not selected_indices:
                                logger.warning("GPT 파싱 실패 - 원본 결과 반환")
                                return stores[:max_results]

                            # 선택된 순번대로 매장 재정렬
                            filtered_stores = [stores[idx - 1] for idx in selected_indices if 1 <= idx <= len(stores)]

                            # 필요 시 원본으로 부족분 채우기 (옵션)
                            if fill_with_original and len(filtered_stores) < max_results:
                                added = []
                                for s in stores:
                                    if s not in filtered_stores:
                                        added.append(s)
                                    if len(filtered_stores) + len(added) >= max_results:
                                        break
                                filtered_stores.extend(added[: max_results - len(filtered_stores)])

                            # 최종 반환: fill_with_original=False면 GPT가 선택한 개수만 반환
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
            menu = store.get('메뉴', '정보없음')
            if menu and menu != '정보없음':
                line = f"{store['순번']}. {store['이름']} | 카테고리: {store['카테고리']} | 메뉴: {menu[:120]} | 주소: {store['주소']}"
            else:
                line = f"{store['순번']}. {store['이름']} | 카테고리: {store['카테고리']} | ⚠️ 메뉴 정보 없음 | 주소: {store['주소']}"
            lines.append(line)
        return "\n".join(lines)

    def _parse_gpt_selection(self, gpt_output: str, total_count: int) -> List[int]:
        """
        GPT 응답에서 선택된 순번 파싱
        """
        try:
            import re
            numbers_str = re.findall(r'\d+', gpt_output)
            selected = [int(n) for n in numbers_str if n.isdigit()]
            valid_selected = [n for n in selected if 1 <= n <= total_count]
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