"""
강남구 매장에 GPT-4.1을 활용한 랜덤 리뷰 추가 스크립트
"""
import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta

import aiohttp
from dotenv import load_dotenv

from src.domain.dto.review.review_dto import RequestCreateReviewDTO
from src.domain.entities.reviews_entity import ReviewsEntity
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.logger.custom_logger import get_logger
from src.utils.path import path_dic

load_dotenv(dotenv_path=path_dic["env"])
logger = get_logger(__name__)


class ReviewGenerator:
    """GPT-4.1을 사용하여 매장 타입별 리뷰를 생성하는 클래스"""
    
    # 매장 타입 매핑
    TYPE_NAMES = {
        0: "음식점",
        1: "카페",
        2: "콘텐츠(관광지/체험)",
        3: "기타"
    }
    
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
            raise ValueError("COPILOT_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
    
    async def generate_review(
        self, 
        category_name: str, 
        category_type: int, 
        sub_category: str, 
        stars: int,
        max_retries: int = 10
    ) -> str:
        """
        매장 정보와 별점에 맞는 리뷰를 GPT-4.1로 생성
        
        Args:
            category_name: 매장명
            category_type: 매장 타입 (0: 음식점, 1: 카페, 2: 콘텐츠, 3: 기타)
            sub_category: 서브 카테고리
            stars: 별점 (1-5)
            max_retries: 최대 재시도 횟수
            
        Returns:
            str: 생성된 리뷰 내용
        """
        type_name = self.TYPE_NAMES.get(category_type, "기타")
        
        # 별점에 따른 감정 톤
        tone_map = {
            5: "매우 만족스럽고 강력 추천하는",
            4: "만족스럽고 긍정적인",
            3: "보통이고 중립적인",
            2: "아쉽고 부정적인",
            1: "매우 실망스럽고 비추천하는"
        }
        
        tone = tone_map.get(stars, "중립적인")
        
        prompt = f"""당신은 실제 방문 후기를 작성하는 고객입니다.

<매장 정보>
- 매장명: {category_name}
- 타입: {type_name}
- 카테고리: {sub_category}
- 별점: {stars}점

<작성 규칙>
1. 위 매장을 실제로 방문한 것처럼 {tone} 톤으로 리뷰를 작성하세요.
2. 매장 타입에 맞는 구체적인 내용을 포함하세요:
   - 음식점: 맛, 메뉴, 양, 가격, 서비스, 분위기
   - 카페: 커피/음료 맛, 디저트, 인테리어, 좌석, 분위기
   - 콘텐츠: 체험 내용, 전시물, 시설, 접근성, 즐길거리
   - 기타: 해당 장소의 특징적인 요소
3. 리뷰는 한국어로 1-3문장, 최대 100자 이내로 작성하세요.
4. 자연스럽고 진솔한 일상 대화체로 작성하세요.
5. 이모지나 특수문자는 사용하지 마세요.

리뷰:"""
        
        payload = {
            "model": "gpt-4.1",
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 다양한 장소를 방문하고 솔직한 리뷰를 작성하는 일반 고객입니다. 자연스럽고 진솔한 한국어 리뷰를 작성하세요."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.8,
            "max_tokens": 150
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
                            review_text = result['choices'][0]['message']['content'].strip()
                            
                            # 리뷰 텍스트 정제
                            review_text = review_text.replace('"', '').replace("'", '')
                            review_text = review_text[:200]  # 최대 길이 제한
                            
                            return review_text
                        else:
                            logger.warning(f"리뷰 생성 API 호출 실패 ({attempt}번째 시도) - 상태 코드: {response.status}")
                            
                            if attempt < max_retries:
                                await asyncio.sleep(1)
                            else:
                                return self._get_fallback_review(stars)
                
            except asyncio.TimeoutError:
                logger.warning(f"리뷰 생성 API 시간 초과 ({attempt}번째 시도)")
                
                if attempt < max_retries:
                    await asyncio.sleep(1)
                else:
                    return self._get_fallback_review(stars)
                    
            except Exception as e:
                logger.error(f"리뷰 생성 중 오류 ({attempt}번째 시도): {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(1)
                else:
                    return self._get_fallback_review(stars)
        
        return self._get_fallback_review(stars)
    
    def _get_fallback_review(self, stars: int) -> str:
        """API 호출 실패 시 기본 리뷰 반환"""
        fallback_reviews = {
            5: ["정말 좋았어요! 강력 추천합니다.", "최고예요. 또 방문하고 싶어요.", "완전 만족스러웠습니다."],
            4: ["좋았어요. 추천합니다.", "만족스러운 곳이에요.", "괜찮았어요. 재방문 의향 있어요."],
            3: ["그냥 무난했어요.", "보통이에요.", "나쁘지 않았어요."],
            2: ["별로였어요.", "기대에 못 미쳤어요.", "아쉬웠습니다."],
            1: ["실망스러웠어요.", "비추천합니다.", "다시는 안 갈 것 같아요."]
        }
        return random.choice(fallback_reviews.get(stars, ["보통이에요."]))


async def add_random_reviews_to_gangnam():
    """
    강남구 매장에 GPT-4.1로 생성한 랜덤 리뷰 추가
    - 매장당 1~5개의 리뷰
    - 각 리뷰는 1~5점 랜덤
    - 리뷰 내용은 GPT-4.1이 매장 타입에 맞게 생성
    - user_id는 'review1234'로 고정
    """
    category_repo = CategoryRepository()
    review_repo = ReviewsRepository()
    review_generator = ReviewGenerator()
    
    # 고정된 user_id
    USER_ID = "review1234"
    
    # 1. 강남구 매장 조회
    logger.info("강남구 매장 조회 중...")
    print("강남구 매장 조회 중...")
    
    gangnam_categories = await category_repo.select(gu="강남구")
    
    if not gangnam_categories:
        logger.warning("강남구 매장이 없습니다.")
        print("강남구 매장이 없습니다.")
        return
    
    logger.info(f"총 {len(gangnam_categories)}개의 강남구 매장을 찾았습니다.")
    print(f"총 {len(gangnam_categories)}개의 강남구 매장을 찾았습니다.")
    print(f"리뷰 작성자 ID: {USER_ID}")
    
    total_reviews_added = 0
    failed_count = 0
    
    # 2. 각 매장에 랜덤 리뷰 추가
    for idx, category in enumerate(gangnam_categories, 1):
        # 매장당 1~5개의 리뷰 개수 랜덤 결정
        num_reviews = random.randint(1, 5)
        
        category_type = category.type if hasattr(category, 'type') and category.type is not None else 3
        type_name = ReviewGenerator.TYPE_NAMES.get(category_type, "기타")
        
        logger.info(f"[{idx}/{len(gangnam_categories)}] 매장: {category.name} (타입: {type_name}) - {num_reviews}개 리뷰 추가 중...")
        print(f"\n[{idx}/{len(gangnam_categories)}] 매장: {category.name} (타입: {type_name})")
        print(f"  카테고리: {category.sub_category}")
        print(f"  {num_reviews}개 리뷰 추가 중...")
        
        for i in range(num_reviews):
            # 별점 랜덤 (1~5점)
            stars = random.randint(1, 5)
            
            try:
                # GPT-4.1로 리뷰 생성
                review_comment = await review_generator.generate_review(
                    category_name=category.name,
                    category_type=category_type,
                    sub_category=category.sub_category,
                    stars=stars
                )
                
                logger.info(f"  생성된 리뷰 ({stars}점): {review_comment}")
                print(f"  ✓ 리뷰 {i+1}/{num_reviews} 생성 완료 (별점: {stars}점)")
                print(f"    내용: {review_comment}")
                
                # 리뷰 엔티티 직접 생성 (user_id는 review1234로 고정)
                review_entity = ReviewsEntity(
                    id=str(uuid.uuid4()),
                    category_id=category.id,
                    user_id=USER_ID,  # 고정된 user_id
                    stars=stars,
                    comments=review_comment,
                    created_at=generate_random_date()
                )
                
                await review_repo.insert(review_entity)
                total_reviews_added += 1
                
                # API 부하 방지를 위한 딜레이
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"  리뷰 추가 실패: {e}")
                print(f"  ✗ 리뷰 {i+1}/{num_reviews} 추가 실패: {e}")
                failed_count += 1
        
        # 매장 간 짧은 딜레이
        await asyncio.sleep(0.5)
    
    # 결과 출력
    logger.info(f"작업 완료 - 총 {total_reviews_added}개 리뷰 추가, {failed_count}개 실패")
    print(f"\n{'='*60}")
    print(f"✅ 작업 완료!")
    print(f"총 {total_reviews_added}개의 리뷰가 추가되었습니다.")
    print(f"작성자 ID: {USER_ID}")
    if failed_count > 0:
        print(f"⚠️  {failed_count}개의 리뷰 추가 실패")
    print(f"{'='*60}")


def generate_random_date() -> datetime:
    """최근 3개월 내 랜덤 날짜 생성"""
    today = datetime.now()
    days_ago = random.randint(0, 90)  # 0~90일 전
    random_date = today - timedelta(days=days_ago)
    
    # 랜덤 시간 추가
    random_hour = random.randint(9, 22)  # 오전 9시 ~ 오후 10시
    random_minute = random.randint(0, 59)
    
    return random_date.replace(hour=random_hour, minute=random_minute, second=0, microsecond=0)


if __name__ == "__main__":
    print("="*60)
    print("강남구 매장에 AI 생성 리뷰 추가 시작")
    print("="*60)
    
    try:
        asyncio.run(add_random_reviews_to_gangnam())
    except KeyboardInterrupt:
        print("\n\n작업이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}")
        print(f"\n오류 발생: {e}")