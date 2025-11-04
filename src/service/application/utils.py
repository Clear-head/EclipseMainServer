"""
태그 추출, 추천 생성 함수
"""

import re
from typing import Dict, List, Tuple

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .prompts import SYSTEM_PROMPT, get_category_prompt, VALIDATION_PROMPT, RESPONSE_MESSAGES

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
# 입력 검증 함수 (하이브리드 방식)
# =============================================================================

# 검증 실패 시 표시할 메시지 (prompts.py에서 관리)
VALIDATION_MESSAGES = RESPONSE_MESSAGES["validation"]


def quick_validation(user_message: str) -> Tuple[bool, str]:
    """
    1차 검증: 규칙 기반 빠른 필터링
    명백히 무의미한 입력을 즉시 걸러냄
    
    Args:
        user_message: 사용자 입력 메시지
        
    Returns:
        (is_valid, error_message)
        - is_valid: True면 유효, False면 무효
        - error_message: 검증 실패 시 사용자에게 보여줄 메시지
    """
    text = user_message.strip()
    
    # 1. 최소 길이 체크 (2자 미만)
    if len(text) < 2:
        return False, VALIDATION_MESSAGES["too_short"]
    
    # 2. 최대 길이 체크 (500자 초과)
    if len(text) > 500:
        return False, VALIDATION_MESSAGES["too_long"]
    
    # 3. 특수문자만 있는지 체크
    if re.match(r'^[^\w\s가-힣]+$', text, re.UNICODE):
        return False, VALIDATION_MESSAGES["only_special_chars"]
    
    # 4. 숫자만 있는지 체크
    if text.isdigit():
        return False, VALIDATION_MESSAGES["only_numbers"]
    
    # 5. 키보드 무작위 입력 패턴 감지
    keyboard_patterns = [
        'asdf', 'asd', 'qwer', 'zxcv', 'qwe', 'zxc',
        'jkl', 'uiop', 'ㅁㄴㅇ', 'ㅂㅈㄷ', 'ㅋㅋㅋㅋㅋ',
        'ㅎㅎㅎㅎㅎ', 'ㄱㄱㄱㄱ', 'ㅇㅇㅇㅇ'
    ]
    text_lower = text.lower()
    for pattern in keyboard_patterns:
        if pattern in text_lower and len(text) <= 10:
            return False, VALIDATION_MESSAGES["keyboard_pattern"]
    
    # 6. 같은 문자 반복 체크 (70% 이상 동일 문자)
    if len(text) >= 3:
        char_counts = {}
        for char in text:
            if char.strip():  # 공백 제외
                char_counts[char] = char_counts.get(char, 0) + 1
        
        if char_counts:
            max_count = max(char_counts.values())
            if max_count / len(text.replace(' ', '')) > 0.7:
                return False, VALIDATION_MESSAGES["repetitive"]
    
    # 7. 의미있는 문자 비율 체크 (한글, 영문, 숫자가 50% 이상)
    meaningful_chars = re.findall(r'[a-zA-Z가-힣0-9]', text)
    if len(meaningful_chars) / len(text) < 0.5:
        return False, VALIDATION_MESSAGES["only_special_chars"]
    
    # 모든 체크 통과
    return True, ""


def llm_validation(user_message: str, category: str) -> Tuple[bool, str]:
    """
    2차 검증: LLM 기반 정밀 검증
    애매한 케이스를 LLM으로 판단
    
    Args:
        user_message: 사용자 입력 메시지
        category: 현재 카테고리 (카페, 음식점, 콘텐츠)
        
    Returns:
        (is_valid, error_message)
    """
    try:
        prompt = VALIDATION_PROMPT.format(
            user_input=user_message,
            category=category
        )
        
        response = chain.invoke({"user_input": prompt})
        response_lower = response.strip().lower()
        
        # LLM 응답 파싱
        if "의미없음" in response_lower or "무의미" in response_lower or "invalid" in response_lower:
            return False, VALIDATION_MESSAGES["ambiguous"]
        else:
            return True, ""
            
    except Exception as e:
        # LLM 오류 시 관대하게 처리 (통과시킴)
        print(f"LLM 검증 오류: {e}")
        return True, ""


def validate_user_input(user_message: str, category: str = "카페") -> Tuple[bool, str]:
    """
    하이브리드 입력 검증 함수 (통합)
    
    1단계: 규칙 기반 빠른 필터링 (quick_validation)
    2단계: 짧거나 애매한 입력은 LLM 검증 (llm_validation)
    
    Args:
        user_message: 사용자 입력 메시지
        category: 현재 카테고리
        
    Returns:
        (is_valid, error_message)
    """
    # 1단계: 규칙 기반 검증 (명백히 무의미한 것만 차단)
    is_valid, error_msg = quick_validation(user_message)
    
    if not is_valid:
        # 명백히 무효한 입력 -> 즉시 거부 (LLM 호출 안 함)
        return False, error_msg
    
    # 2단계: 짧거나 애매한 케이스는 LLM 검증
    
    # 특수문자/공백 제거 후 실제 문자 수 확인
    text_without_special = re.sub(r'[^\w가-힣]', '', user_message, flags=re.UNICODE)
    is_short = len(text_without_special) <= 5  # 5자 이하면 짧다고 판단
    
    # 애매한 키워드 체크
    ambiguous_keywords = [
        "아무거나", "몰라", "글쎄", "모르겠어", "아무데나", "상관없어",
        "그냥", "막", "아무", "whatever", "anything", "idk", "dunno"
    ]
    
    text_lower = user_message.lower()
    has_ambiguous_keyword = any(keyword in text_lower for keyword in ambiguous_keywords)
    
    # ✨ 짧거나 애매한 키워드가 있으면 LLM에게 판단시키기
    if is_short or has_ambiguous_keyword:
        print(f"🤖 LLM 검증 시작: '{user_message}' (짧은 입력: {is_short}, 애매한 키워드: {has_ambiguous_keyword})")
        return llm_validation(user_message, category)
    
    # 명백히 의미있는 입력 (6자 이상 + 애매한 키워드 없음) -> 통과
    return True, ""


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
        if len(tag_list) < 2:
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
