"""
LLM을 사용한 카테고리 타입 분류 서비스
"""
import os
import asyncio
import aiohttp
import re
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(dotenv_path="src/.env")

from src.utils.path import path_dic
from src.logger.custom_logger import get_logger

load_dotenv(dotenv_path=path_dic["env"])
logger = get_logger(__name__)

class CategoryTypeClassifier:
    """LLM을 사용하여 서브 카테고리를 분류하는 클래스"""
    
    def __init__(self):
        self.api_token = os.getenv('COPILOT_API_KEY')
        if self.api_token:
            self.api_endpoint = "https://api.githubcopilot.com/chat/completions"
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        else:
            logger.warning("GitHub API 토큰이 없습니다. 카테고리 분류 기능이 비활성화됩니다.")
    
    async def classify_category_type(self, sub_category: str, max_retries: int = 10) -> int:
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
- 카페 (카페, 커피, 디저트, 베이커리, 빵집, 차 등) → 1
- 콘텐츠 (관광지, 박물관, 미술관, 공원, 놀이공원, 체험관, 전시관, 테마파크, 복합문화공간, 공방, 기념물, 놀거리, 동물카페, 운동 등) → 2
- 분류하기 힘든 경우 (케이크전문, 화장실, 공장, 빌딩, 반려동물호텔, 컴퓨터수리 등) → 3

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
                                return category_type
                            else:
                                logger.warning(f"유효하지 않은 응답: {category_type_str}, 기본값 3 반환")
                                return 3
                        else:
                            logger.warning(f"카테고리 분류 API 호출 실패 ({attempt}번째 시도) - 상태 코드: {response.status}")
                            
                            if attempt < max_retries:
                                await asyncio.sleep(1)
                            else:
                                logger.error(f"최대 재시도 횟수({max_retries}회) 초과 - 기본값 3 반환")
                                return 3
                
            except asyncio.TimeoutError:
                logger.warning(f"카테고리 분류 API 시간 초과 ({attempt}번째 시도)")
                
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.error(f"최대 재시도 횟수({max_retries}회) 초과 - 기본값 3 반환")
                    return 3
                    
            except Exception as e:
                logger.error(f"카테고리 분류 중 오류 ({attempt}번째 시도): {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.error(f"최대 재시도 횟수({max_retries}회) 초과 - 기본값 3 반환")
                    return 3
        
        return 3