"""
태그 추출, 추천 생성 함수
"""

import re
from typing import Dict, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .prompts import SYSTEM_PROMPT, get_category_prompt

RECOMMENDATION_DATABASE = {
    "카페": {
        "조용한": ["조용한 카페", "사일런트 카페", "조용한 공간"],
        "공부": ["스터디 카페", "학습 카페", "집중 카페"],
        "와이파이": ["와이파이 카페", "인터넷 카페", "디지털 카페"],
        "라떼": ["라떼 전문점", "바리스타 카페", "프리미엄 카페"],
        "케이크": ["디저트 카페", "케이크 전문점", "스위트 카페"],
        "뷰": ["뷰 카페", "전망 카페", "루프탑 카페"],
        "아늑한": ["아늑한 카페", "코지 카페", "홈 카페"],
        "모던한": ["모던 카페", "트렌디 카페", "컨템포러리 카페"],
        "치즈케이크": ["디저트 카페", "케이크 전문점", "스위트 카페"],
        "고구마 라떼": ["라떼 전문점", "바리스타 카페", "프리미엄 카페"],
        "바닐라 라떼": ["라떼 전문점", "바리스타 카페", "프리미엄 카페"],
        "초코케이크": ["디저트 카페", "케이크 전문점", "스위트 카페"]
    },
    "음식점": {
        "한식": ["전통 한식당", "정통 한식", "한국 요리"],
        "중식": ["중화요리", "중국집", "차이나"],
        "일식": ["일본 요리", "스시", "라멘"],
        "양식": ["서양 요리", "스테이크 하우스", "이탈리안"],
        "데이트": ["데이트 레스토랑", "로맨틱 레스토랑", "커플 레스토랑"],
        "가족": ["가족 레스토랑", "패밀리 레스토랑", "아이 친화적"],
        "저렴한": ["저렴한 식당", "가성비 식당", "맛집"],
        "고급": ["고급 레스토랑", "파인 다이닝", "럭셔리 레스토랑"]
    },
    "콘텐츠": {
        "영화": ["영화관", "시네마", "멀티플렉스"],
        "전시회": ["미술관", "박물관", "갤러리"],
        "공연": ["콘서트홀", "극장", "공연장"],
        "게임": ["게임카페", "PC방", "보드게임카페"],
        "쇼핑": ["쇼핑몰", "상가", "마켓"],
        "액션": ["액션 영화", "스릴러", "모험"],
        "로맨스": ["로맨스 영화", "멜로", "러브스토리"],
        "코미디": ["코미디 영화", "개그", "유머"]
    }
}



# =============================================================================
# LLM 체인 초기화
# =============================================================================

def setup_chain():
    import os
    import sys
    import io
    from dotenv import load_dotenv

    # 환경 설정
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")

    # 한글 인코딩 설정 (Windows 환경에서 한글 출력 문제 해결)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    """
    LangChain 기반 LLM 체인 초기화

    GPT-4o-mini 모델을 사용하여 시스템 프롬프트 + 사용자 입력을 처리하는
    체인을 구성. Temperature 0.1로 설정해서 일관성 있는 태그 추출
    """
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_key=openai_api_key,
        temperature=0.1  # 낮은 온도로 일관된 결과 보장
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", "{user_input}")
    ])

    output_parser = StrOutputParser()
    return prompt_template | llm | output_parser


# 전역 LLM 체인 인스턴스 (앱 시작 시 한 번만 초기화)
chain = setup_chain()


# =============================================================================
# 태그 추출 함수
# =============================================================================

def extract_tags_by_category(user_detail: str, category: str, people_count: int = 1) -> List[str]:
    """
    카테고리별 맞춤 프롬프트로 LLM을 사용해 태그 추출

    각 카테고리(카페, 음식점, 콘텐츠)마다 다른 키워드 우선순위를 적용해서
    더 정확한 태그를 추출. 예를 들어 카페는 분위기/용도/시설 중심,
    음식점은 음식종류/메뉴/가격대 중심으로 추출

    Args:
        user_detail: 사용자가 입력한 문장
        category: 카테고리명
        people_count: 함께 활동할 인원 수

    Returns:
        추출된 태그 리스트 (5-6개)
    """
    try:
        base_prompt = get_category_prompt(category, user_detail, people_count)

        tag_response = chain.invoke({"user_input": base_prompt})
        tag_list = [tag.strip() for tag in tag_response.split(",") if tag.strip()]

        # 태그가 너무 적으면 재시도
        if len(tag_list) < 3:
            tag_response = chain.invoke({"user_input": base_prompt})
            tag_list = [tag.strip() for tag in tag_response.split(",") if tag.strip()]

        # 최소 1개는 보장
        if len(tag_list) == 0:
            tag_list = [user_detail.strip()[:10]]

        return tag_list

    except Exception as e:
        # 오류 발생 시 기본 태그 반환
        fallback_tag = [user_detail.strip()[:10]] if user_detail.strip() else ["일반적인"]
        return fallback_tag


# =============================================================================
# 추천 생성 함수
# =============================================================================

def generate_recommendations_by_category_hardcoded(category: str, tags: List[str]) -> str:
    """
    카테고리와 태그를 기반으로 추천 장소 생성 (하드코딩 버전)

    Args:
        category: 카테고리 이름 (예: "카페", "음식점")
        tags: 추출된 태그 리스트 (예: ["조용한", "와이파이"])

    Returns:
        추천 장소 문자열 (예: "1. 조용한 카페, 2. 사일런트 카페, 3. 조용한 공간")
    """
    if category not in RECOMMENDATION_DATABASE:
        return f"1. 일반적인 {category}, 2. 추천 {category}, 3. 인기 {category}"

    recommendations = []
    used_recommendations = set()

    # 태그별로 추천 찾기
    for tag in tags:
        if tag in RECOMMENDATION_DATABASE[category]:
            for rec in RECOMMENDATION_DATABASE[category][tag]:
                if rec not in used_recommendations:
                    recommendations.append(rec)
                    used_recommendations.add(rec)
                    if len(recommendations) >= 3:
                        break
        if len(recommendations) >= 3:
            break

    # 추천이 부족하면 기본 추천 추가
    if len(recommendations) < 3:
        default_recommendations = [
            f"추천 {category}",
            f"인기 {category}",
            f"베스트 {category}"
        ]
        for default_rec in default_recommendations:
            if default_rec not in used_recommendations:
                recommendations.append(default_rec)
                if len(recommendations) >= 3:
                    break

    # 형식에 맞게 변환
    formatted_recommendations = ", ".join([f"{i + 1}. {rec}" for i, rec in enumerate(recommendations[:3])])
    return formatted_recommendations


def generate_recommendations_by_category(category: str, tags: List[str]) -> str:
    """
    카테고리별 추천 생성 (하드코딩 버전 래퍼)

    추후 DB나 외부 API로 변경 시 이 함수만 수정하면 됨
    """
    return generate_recommendations_by_category_hardcoded(category, tags)


def generate_recommendations(selected_activities: List[str], collected_tags: Dict[str, List[str]]) -> str:
    """
    모든 카테고리에 대한 최종 추천 생성

    수집된 태그를 바탕으로 각 카테고리별 추천을 생성하고
    하나의 문자열로 합쳐서 반환

    Args:
        selected_activities: 선택한 활동 카테고리 리스트
        collected_tags: 카테고리별로 수집된 태그 딕셔너리

    Returns:
        전체 추천 결과 문자열
    """
    all_recommendations = []

    # 각 카테고리별로 추천 생성
    for category in selected_activities:
        if category in collected_tags and collected_tags[category]:
            category_recommendations = generate_recommendations_by_category(category, collected_tags[category])
            all_recommendations.append(f"{category}: {category_recommendations}")
        else:
            default_tags = ["일반적인", "추천", "인기"]
            category_recommendations = generate_recommendations_by_category(category, default_tags)
            all_recommendations.append(f"{category}: {category_recommendations}")

    final_recommendations = "\n".join(all_recommendations)
    return final_recommendations


def parse_recommendations(recommendations_text: str, selected_activities: List[str]) -> Dict[str, List[str]]:
    """
    추천 결과 문자열을 Flutter가 사용할 수 있는 딕셔너리로 변환

    "카페: 1. 조용한 카페, 2. 사일런트 카페, 3. 조용한 공간" 형태의 문자열을
    {"카페": ["조용한 카페", "사일런트 카페", "조용한 공간"]} 형태로 파싱

    Args:
        recommendations_text: 전체 추천 결과 문자열
        selected_activities: 카테고리 리스트

    Returns:
        카테고리별 추천 장소 딕셔너리
    """
    result = {}
    lines = recommendations_text.strip().split('\n')

    for line in lines:
        if not line.strip():
            continue

        for category in selected_activities:
            if line.strip().startswith(category):
                # "카테고리: 1. 장소1, 2. 장소2, 3. 장소3" 형식 파싱
                content = line.split(':', 1)[1].strip() if ':' in line else line

                # 숫자와 점 제거하여 장소명만 추출
                places = []
                for part in content.split(','):
                    place = part.strip()
                    # "1. 장소명" -> "장소명" 형태로 변환
                    place = re.sub(r'^\d+\.\s*', '', place)
                    if place:
                        places.append(place)

                result[category] = places
                break

    return result


# =============================================================================
# 수집 데이터 구조화 함수
# =============================================================================

def format_collected_data_for_server(session: Dict) -> List[Dict]:
    """
    세션 데이터를 서버로 전송할 형식으로 구조화
    
    채팅 완료 후 수집된 정보(위치, 인원수, 카테고리별 키워드)를
    카테고리별로 구조화된 리스트로 변환합니다.
    
    Args:
        session: 세션 딕셔너리 (play_address, peopleCount, selectedCategories, collectedTags 포함)
    
    Returns:
        카테고리별로 구조화된 데이터 리스트
        예시:
        [
            {
                "위치": "강남구",
                "인원수": "2명",
                "카테고리 타입": "카페",
                "키워드": ["치즈케이크", "고구마 라떼", "한적한", "디저트"]
            },
            {
                "위치": "강남구",
                "인원수": "2명",
                "카테고리 타입": "음식점",
                "키워드": ["된장찌개", "돼지고기", "냉면", "한식", "구이"]
            }
        ]
    """
    # 세션에서 기본 정보 추출
    play_address = session.get("play_address", "")
    people_count = session.get("peopleCount", 1)
    selected_categories = session.get("selectedCategories", [])
    collected_tags = session.get("collectedTags", {})
    
    # 인원수 포맷팅 ("2명" 형식)
    people_count_str = f"{people_count}명"
    
    # 결과 리스트 초기화
    formatted_data = []
    
    # 각 카테고리별로 데이터 구조화
    for category in selected_categories:
        # 카테고리별 키워드 추출 (없으면 빈 리스트)
        keywords = collected_tags.get(category, [])
        
        # 각 카테고리별 객체 생성
        category_data = {
            "위치": play_address,
            "인원수": people_count_str,
            "카테고리 타입": category,
            "키워드": keywords
        }
        
        formatted_data.append(category_data)
    
    return formatted_data
