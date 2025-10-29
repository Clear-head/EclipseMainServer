"""
Copilot API를 사용한 검색 쿼리 개선 서비스
"""
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from typing import Optional

# 환경 변수 로드
load_dotenv(dotenv_path="src/.env")

from src.logger.custom_logger import get_logger
logger = get_logger(__name__)


class QueryEnhancementService:
    """사용자 입력을 자연스러운 검색 쿼리로 변환하는 클래스"""
    
    def __init__(self):
        self.api_token = os.getenv('COPILOT_API_KEY') or os.getenv('GITHUB_TOKEN')
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
사용자의 입력을 검색에 최적화된 간결한 한국어로 변환하세요.

중요 규칙:
- 핵심 키워드만 간결하게 유지 (과도한 설명 금지)
- 형용사 형태로 자연스럽게 연결
- 2-4단어로 구성 (너무 길면 검색 정확도 떨어짐)
- 구어체나 띄어쓰기 오류만 수정
- 한국어로만 답변"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 50
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
        
        prompt = f"""다음 사용자 입력을 검색에 최적화된 간결한 한국어로 변환하세요.

<사용자 입력>
{user_keyword}

<상황 정보>
{context}

<변환 규칙>
1. 핵심 키워드만 유지 (2-4단어)
2. 1명일 때만 "혼자" 키워드 포함
3. 형용사 형태로 자연스럽게 연결
4. 쉼표나 불필요한 조사 제거

<변환 예시>
입력: "조용하고 분위기좋은곳" (1명)
출력: 혼자 가기 좋은 조용한 곳

입력: "조용하고 분위기좋은곳" (2명 이상)
출력: 조용하고 분위기 좋은

입력: "혼밥하기좋고 맛있는곳" (1명)
출력: 혼자 식사하기 좋은

입력: "데이트하기딱좋음" (2명)
출력: 데이트하기 좋은

입력: "삼겹살, 저렴한, 된장찌개" (2명 이상, 음식점)
출력: 저렴한 삼겹살 된장찌개

입력: "쑥라떼, 에끌레어" (2명 이상, 카페)
출력: 쑥라떼 에끌레어

입력: "커피맛있고 조용한" (2명 이상, 카페)
출력: 커피 맛있고 조용한

❌ 나쁜 예시: "저렴한 가격에 삼겹살과 된장찌개를 함께 즐길 수 있는 음식점" (너무 김)
✅ 좋은 예시: "저렴한 삼겹살 된장찌개" (간결함)

변환된 검색어 (2-4단어, 한국어로만):"""
        
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
        
        # 사용자 키워드 (쉼표 제거하고 공백으로)
        if user_keyword and user_keyword.strip():
            keywords = user_keyword.strip().replace(",", " ")
            # 연속된 공백 제거
            keywords = " ".join(keywords.split())
            query_parts.append(keywords)
        
        final_query = " ".join(query_parts) if query_parts else "추천"
        
        return final_query