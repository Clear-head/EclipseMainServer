"""
프롬프트 태그화 성능 테스트 스크립트

이 스크립트는 prompts.py의 프롬프트를 수정하고 
태그화 성능을 테스트하는 데 사용됩니다.

사용법:
1. prompts.py를 수정합니다
2. 이 스크립트를 실행하여 결과를 확인합니다
3. 원하는 결과가 나올 때까지 반복합니다

실행: python test_prompt_tagging.py
"""

import os
import sys
from typing import List, Dict
from dotenv import load_dotenv

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.service.application.utils import extract_tags_by_category

# 환경 변수 로드
load_dotenv()

# =============================================================================
# 테스트 케이스 정의
# =============================================================================

TEST_CASES = {
    "카페": [
        {
            "input": "치즈케익이 맛있고, 고구마 라떼가 있었으면 좋겠어. 그리고 한적하고, 뷰가 좋았으면 좋겠어.",
            "people_count": 2,
            "description": "디저트 + 분위기 조합"
        },
        {
            "input": "공부하기 좋고 콘센트 많고 와이파이 빠른 곳",
            "people_count": 1,
            "description": "학습 용도"
        },
        {
            "input": "친구랑 수다 떨기 좋은 아늑한 카페",
            "people_count": 2,
            "description": "대화 중심"
        },
        {
            "input": "바닐라 라떼가 맛있고, 초코케익이 있었으면 좋겠어.",
            "people_count": 1,
            "description": "음료 + 디저트"
        },
        {
            "input": "탁 트인 뷰가 좋고, 음악이 잔잔했으면 좋겠어.",
            "people_count": 2,
            "description": "분위기 중심"
        }
    ],
    "음식점": [
        {
            "input": "둘이 먹다 하나 죽어도 모를 것 같은 맛있는 김치찌개랑 돼지고기 삼겹살을 먹고 싶어.",
            "people_count": 2,
            "description": "비유적 표현 포함"
        },
        {
            "input": "커피 맛이 진하고 좌석이 편한 곳이 좋아.",
            "people_count": 1,
            "description": "맛 특징 + 시설"
        },
        {
            "input": "매운 떡볶이랑 튀김 먹고 싶어",
            "people_count": 3,
            "description": "분식 메뉴"
        },
        {
            "input": "신선한 초밥이랑 사시미를 먹을 수 있는 고급스러운 곳",
            "people_count": 2,
            "description": "일식 + 고급"
        },
        {
            "input": "가족들이랑 저녁 먹을 건데 테이블이 넓고 조용한 한식당",
            "people_count": 5,
            "description": "가족 모임"
        }
    ],
    "콘텐츠": [
        {
            "input": "재미있는 액션 영화 보고 싶어",
            "people_count": 2,
            "description": "영화 관람"
        },
        {
            "input": "감성적인 전시회나 갤러리 가고 싶어",
            "people_count": 1,
            "description": "전시 관람"
        },
        {
            "input": "친구들이랑 보드게임 카페 가서 놀고 싶어",
            "people_count": 4,
            "description": "그룹 활동"
        }
    ]
}

# =============================================================================
# 출력 포맷팅 함수
# =============================================================================

def print_header(title: str):
    """섹션 헤더 출력"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_test_case(category: str, case: Dict, tags: List[str]):
    """테스트 케이스 결과 출력"""
    print(f"\n[{category}] {case['description']}")
    print(f"  입력: {case['input']}")
    print(f"  인원: {case['people_count']}명")
    print(f"  태그: {', '.join(tags)}")
    print(f"  개수: {len(tags)}개")
    
    # 경고 표시
    if len(tags) < 3:
        print("  ⚠️  경고: 태그가 3개 미만입니다!")
    elif len(tags) > 8:
        print("  ⚠️  경고: 태그가 8개를 초과합니다!")


def print_summary(results: Dict):
    """테스트 결과 요약 출력"""
    print_header("테스트 결과 요약")
    
    total_tests = 0
    total_tags = 0
    warnings = 0
    
    for category, cases in results.items():
        category_total = len(cases)
        category_tags = sum(len(case['tags']) for case in cases)
        category_warnings = sum(1 for case in cases if len(case['tags']) < 3 or len(case['tags']) > 8)
        
        total_tests += category_total
        total_tags += category_tags
        warnings += category_warnings
        
        avg_tags = category_tags / category_total if category_total > 0 else 0
        
        print(f"\n[{category}]")
        print(f"  테스트 케이스: {category_total}개")
        print(f"  평균 태그 수: {avg_tags:.1f}개")
        print(f"  경고: {category_warnings}개")
    
    print(f"\n전체 통계:")
    print(f"  총 테스트: {total_tests}개")
    print(f"  총 태그: {total_tags}개")
    print(f"  평균 태그: {total_tags / total_tests if total_tests > 0 else 0:.1f}개")
    print(f"  경고: {warnings}개")
    
    if warnings == 0:
        print("\n✅ 모든 테스트가 정상적으로 완료되었습니다!")
    else:
        print(f"\n⚠️  {warnings}개의 경고가 있습니다. 프롬프트 조정이 필요할 수 있습니다.")


# =============================================================================
# 메인 테스트 함수
# =============================================================================

def run_tests():
    """모든 테스트 케이스 실행"""
    print_header("프롬프트 태그화 성능 테스트 시작")
    
    results = {}
    
    # 각 카테고리별 테스트 실행
    for category, test_cases in TEST_CASES.items():
        print_header(f"{category} 카테고리 테스트")
        
        category_results = []
        
        for case in test_cases:
            try:
                # 태그 추출 실행
                tags = extract_tags_by_category(
                    user_detail=case['input'],
                    category=category,
                    people_count=case['people_count']
                )
                
                # 결과 출력
                print_test_case(category, case, tags)
                
                # 결과 저장
                category_results.append({
                    'case': case,
                    'tags': tags
                })
                
            except Exception as e:
                print(f"\n❌ 오류 발생: {e}")
                category_results.append({
                    'case': case,
                    'tags': [],
                    'error': str(e)
                })
        
        results[category] = category_results
    
    # 결과 요약 출력
    print_summary(results)
    
    return results


# =============================================================================
# 커스텀 테스트 함수
# =============================================================================

def test_custom_input():
    """사용자 정의 입력 테스트"""
    print_header("커스텀 입력 테스트")
    print("\n원하는 문장을 입력하고 태그화 결과를 확인하세요.")
    print("종료하려면 'q' 또는 'quit'를 입력하세요.\n")
    
    while True:
        # 사용자 입력 받기
        user_input = input("\n입력 문장: ").strip()
        
        if user_input.lower() in ['q', 'quit', 'exit', '종료']:
            print("\n테스트를 종료합니다.")
            break
        
        if not user_input:
            continue
        
        # 카테고리 선택
        category = input("카테고리 (카페/음식점/콘텐츠, 기본값: 카페): ").strip() or "카페"
        
        # 인원 수 입력
        people_input = input("인원 수 (기본값: 2): ").strip()
        people_count = int(people_input) if people_input.isdigit() else 2
        
        # 태그 추출
        try:
            tags = extract_tags_by_category(
                user_detail=user_input,
                category=category,
                people_count=people_count
            )
            
            print(f"\n결과:")
            print(f"  카테고리: {category}")
            print(f"  인원: {people_count}명")
            print(f"  추출된 태그: {', '.join(tags)}")
            print(f"  태그 개수: {len(tags)}개")
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    print("\n프롬프트 태그화 테스트 도구")
    print("=" * 80)
    print("\n사용 가능한 모드:")
    print("  1. 자동 테스트 - 미리 정의된 테스트 케이스 실행")
    print("  2. 수동 테스트 - 직접 입력하여 테스트")
    print("  3. 둘 다 실행")
    
    mode = input("\n모드 선택 (1/2/3, 기본값: 1): ").strip() or "1"
    
    if mode in ["1", "3"]:
        run_tests()
    
    if mode in ["2", "3"]:
        test_custom_input()
    
    print("\n" + "=" * 80)
    print("테스트 완료!")
    print("=" * 80)

