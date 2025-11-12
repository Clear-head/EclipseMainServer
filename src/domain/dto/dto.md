dto/
├── user/
│   ├── user_auth_dto.py          # 로그인, 회원가입, 토큰
│   ├── user_profile_dto.py       # 프로필 조회/수정
│   └── user_account_dto.py       # 계정 삭제
├── category/
│   ├── category_dto.py           # 카테고리 리스트
│   └── category_detail_dto.py    # 카테고리 상세
├── review/
│   └── review_dto.py             # 리뷰 CRUD 통합
├── like/
│   └── like_dto.py               # 좋아요
├── history/
│   └── history_dto.py            # 방문 기록
├── chat/
│   ├── chat_session_dto.py       # 세션 관리
│   ├── chat_message_dto.py       # 메시지 송수신
│   └── chat_recommendation_dto.py # 추천 결과
├── transport/
│   └── transport_dto.py          # 교통 계산
└── crawl/
    ├── crawl_category_dto.py     # 크롤링 카테고리
    └── crawl_tags_dto.py         # 크롤링 태그