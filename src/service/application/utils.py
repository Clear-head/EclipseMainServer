"""
태그 추출, 추천 생성 함수
"""

from typing import Dict, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .prompts import SYSTEM_PROMPT, get_category_prompt

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
