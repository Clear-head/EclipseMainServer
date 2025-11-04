"""
Flutter 채팅 시뮬레이션 테스트

실제 Flutter 앱에서 채팅하듯이 대화를 진행합니다.
카테고리별로 순차적으로 질문하고, 검증 후 태그를 수집합니다.
최종 결과는 카테고리별로 생성된 태그만 표시합니다.

실행: python quick_test.py
"""

import os
import sys
from dotenv import load_dotenv

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.service.application.utils import extract_tags_by_category, validate_user_input
from src.service.application.prompts import RESPONSE_MESSAGES

# 환경 변수 로드
load_dotenv()


def print_bot_message(message: str, is_warning: bool = False):
    """봇 메시지 출력 (채팅 스타일)"""
    if is_warning:
        print(f"\n🤖 하루 (경고): {message}")
    else:
        print(f"\n🤖 하루: {message}")


def print_user_message(message: str):
    """사용자 메시지 출력 (채팅 스타일)"""
    print(f"\n👤 나: {message}")


def is_yes_response(user_input: str) -> bool:
    """Yes 응답인지 확인"""
    yes_words = ["yes", "네", "넵", "예", "좋아", "좋아요", "그래", "맞아", "ㅇㅇ", "기기", "ㄱㄱ", "고고", "네네", "다음", "응", "어"]
    return any(word in user_input.lower() for word in yes_words)


def is_more_response(user_input: str) -> bool:
    """More(추가) 응답인지 확인"""
    more_words = ["추가", "더", "더해", "추가하기", "추가요", "더할래"]
    return any(word in user_input.lower() for word in more_words)


def handle_user_message(session: dict, user_message: str) -> dict:
    """사용자 메시지 처리 및 태그 생성 (검증 포함)"""
    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]
    
    if current_index >= len(selected_categories):
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True
        return {
            "status": "success",
            "message": RESPONSE_MESSAGES["start"]["all_completed"],
            "stage": "confirming_results",
            "showYesNoButtons": True,
            "yesNoQuestion": RESPONSE_MESSAGES["buttons"]["result_question"]
        }
    
    current_category = selected_categories[current_index]
    
    # 입력 검증
    is_valid, error_message = validate_user_input(user_message, current_category)
    if not is_valid:
        return {
            "status": "validation_failed",
            "message": error_message,
            "stage": "collecting_details",
            "currentCategory": current_category
        }
    
    # 태그 추출
    people_count = session.get("peopleCount", 1)
    new_tags = extract_tags_by_category(user_message, current_category, people_count)
    
    # 세션에 태그 저장
    if "collectedTags" not in session:
        session["collectedTags"] = {}
    
    if current_category in session["collectedTags"]:
        existing_tags = session["collectedTags"][current_category]
        combined_tags = existing_tags + new_tags
        combined_tags = list(dict.fromkeys(combined_tags))  # 중복 제거
        session["collectedTags"][current_category] = combined_tags
    else:
        session["collectedTags"][current_category] = new_tags
    
    tags = session["collectedTags"][current_category]
    message = f"현재까지 수집된 키워드: {', '.join(tags)}"
    
    session["waitingForUserAction"] = True
    
    return {
        "status": "success",
        "message": message,
        "stage": "collecting_details",
        "tags": tags,
        "showYesNoButtons": True,
        "yesNoQuestion": RESPONSE_MESSAGES["buttons"]["yes_no_question"],
        "currentCategory": current_category
    }


def handle_next_category(session: dict) -> dict:
    """다음 카테고리로 이동"""
    session["waitingForUserAction"] = False
    session["currentCategoryIndex"] += 1
    
    selected_categories = session["selectedCategories"]
    
    if session["currentCategoryIndex"] >= len(selected_categories):
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True
        return {
            "status": "success",
            "message": RESPONSE_MESSAGES["start"]["all_completed"],
            "stage": "confirming_results",
            "showYesNoButtons": True,
            "yesNoQuestion": RESPONSE_MESSAGES["buttons"]["result_question"]
        }
    
    next_category = selected_categories[session["currentCategoryIndex"]]
    next_message = RESPONSE_MESSAGES["start"]["next_category"].format(next_category=next_category)
    
    return {
        "status": "success",
        "message": next_message,
        "stage": "collecting_details"
    }


def handle_add_more_tags(session: dict) -> dict:
    """더 많은 태그 추가 요청"""
    session["waitingForUserAction"] = False
    current_index = session["currentCategoryIndex"]
    selected_categories = session["selectedCategories"]
    
    if current_index >= len(selected_categories):
        session["stage"] = "confirming_results"
        session["waitingForUserAction"] = True
        return {
            "status": "success",
            "message": RESPONSE_MESSAGES["start"]["all_completed"],
            "stage": "confirming_results",
            "showYesNoButtons": True,
            "yesNoQuestion": RESPONSE_MESSAGES["buttons"]["result_question"]
        }
    
    current_category = selected_categories[current_index]
    add_more_message = RESPONSE_MESSAGES["start"]["add_more"].format(current_category=current_category)
    
    return {
        "status": "success",
        "message": add_more_message,
        "stage": "collecting_details",
        "currentCategory": current_category
    }


def main():
    print("\n" + "="*80)
    print("  💬 Flutter 채팅 시뮬레이션 테스트")
    print("="*80)
    print("\n실제 Flutter 앱에서 채팅하듯이 대화를 진행합니다.")
    print("카테고리별로 질문하고, 검증 후 태그를 수집합니다.\n")
    
    # 초기 설정
    print("\n" + "-"*80)
    print("📋 초기 설정")
    print("-"*80)
    
    # 위치 입력
    play_address = input("\n📍 위치를 입력하세요 (예: 강남구): ").strip()
    if not play_address:
        play_address = "강남구"
        print(f"   기본값 사용: {play_address}")
    
    # 인원 수 입력
    people_input = input("👥 인원 수를 입력하세요 (기본값: 2): ").strip()
    people_count = int(people_input) if people_input.isdigit() else 2
    print(f"   인원 수: {people_count}명")
    
    # 카테고리 선택
    print("\n📂 활동 카테고리를 선택하세요 (복수 선택 가능, 쉼표로 구분):")
    print("  1. 카페")
    print("  2. 음식점")
    print("  3. 콘텐츠")
    category_input = input("선택 (예: 1,2 또는 1,2,3): ").strip()
    
    category_map = {"1": "카페", "2": "음식점", "3": "콘텐츠"}
    selected_indices = [x.strip() for x in category_input.split(",") if x.strip()]
    selected_categories = [category_map[idx] for idx in selected_indices if idx in category_map]
    
    if not selected_categories:
        selected_categories = ["카페"]
        print("   기본값 사용: 카페")
    else:
        print(f"   선택된 카테고리: {', '.join(selected_categories)}")
    
    # 세션 초기화
    session = {
        "play_address": play_address,
        "peopleCount": people_count,
        "selectedCategories": selected_categories,
        "collectedTags": {},
        "currentCategoryIndex": 0,
        "stage": "collecting_details",
        "waitingForUserAction": False
    }
    
    # 첫 메시지 출력
    first_category = selected_categories[0]
    categories_text = ', '.join(selected_categories)
    first_message = RESPONSE_MESSAGES["start"]["first_message"].format(
        people_count=people_count,
        categories_text=categories_text,
        first_category=first_category
    )
    print_bot_message(first_message)
    
    # 채팅 루프
    print("\n" + "="*80)
    print("  💬 채팅 시작")
    print("="*80)
    print("\n💡 팁:")
    print("   - Yes/No 버튼: '네' 또는 '추가하기'로 입력")
    print("   - 검증 실패 시: 다시 입력하면 됩니다")
    print("   - 종료: 'q' 또는 'quit' 입력\n")
    
    while True:
        # 사용자 입력
        user_input = input("\n👤 입력: ").strip()
        
        if user_input.lower() in ['q', 'quit', 'exit', '종료']:
            print("\n채팅을 종료합니다. 👋\n")
            break
        
        if not user_input:
            print("❌ 문장을 입력해주세요.")
            continue
        
        print_user_message(user_input)
        
        # 버튼 액션 처리
        if session.get("waitingForUserAction", False):
            # 결과 확인 단계
            if session.get("stage") == "confirming_results":
                if is_yes_response(user_input):
                    # 최종 결과 출력
                    print("\n" + "="*80)
                    print("  ✅ 최종 결과 - 카테고리별 태그")
                    print("="*80)
                    
                    collected_tags = session.get("collectedTags", {})
                    if collected_tags:
                        for category, tags in collected_tags.items():
                            print(f"\n📂 {category}:")
                            for i, tag in enumerate(tags, 1):
                                print(f"   {i}. {tag}")
                            print(f"   (총 {len(tags)}개)")
                    else:
                        print("\n⚠️  수집된 태그가 없습니다.")
                    
                    print("\n" + "="*80)
                    print("채팅이 완료되었습니다. 👋\n")
                    break
                else:
                    print_bot_message(RESPONSE_MESSAGES["start"]["unclear_result_response"])
                    continue
            
            # Yes/No 버튼 처리
            is_next = is_yes_response(user_input)
            is_more = is_more_response(user_input)
            
            if is_next and not is_more:
                # 다음 카테고리로 이동
                response = handle_next_category(session)
                print_bot_message(response["message"])
            elif is_more and not is_next:
                # 더 추가하기
                response = handle_add_more_tags(session)
                print_bot_message(response["message"])
            else:
                print_bot_message(RESPONSE_MESSAGES["start"]["unclear_response"])
        else:
            # 일반 메시지 처리 (검증 + 태그 추출)
            response = handle_user_message(session, user_input)
            
            if response["status"] == "validation_failed":
                # 검증 실패
                print_bot_message(response["message"], is_warning=True)
            else:
                # 검증 성공 및 태그 추출 완료
                print_bot_message(response["message"])
                if response.get("showYesNoButtons"):
                    print_bot_message(response.get("yesNoQuestion", ""))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n채팅이 중단되었습니다. 👋\n")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        print(traceback.format_exc())
