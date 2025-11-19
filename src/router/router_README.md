# Router

FastAPI 라우터 레이어로, HTTP 엔드포인트를 정의하고 요청을 서비스 레이어로 전달합니다.

## 구조

```
router/
├── admin/                    # 관리자용 라우터
│   ├── dashboard_controller.py   # 대시보드 통계 API
│   └── monitoring_controller.py  # 모니터링 및 제재
└── users/                    # 사용자용 라우터
    ├── auth_controller.py        # 인증 (로그인/회원가입)
    ├── category_controller.py    # 카테고리(매장) 조회
    ├── user_controller.py        # 사용자 정보 관리
    ├── like_controller.py        # 찜 기능
    ├── history_controller.py     # 일정표 히스토리
    ├── review_controller.py      # 리뷰 관리
    └── service_controller.py     # AI 채팅 서비스
```

## 주요 라우터

### Users

#### auth_controller.py
인증 관련 엔드포인트

```python
POST   /api/auth/session      # 로그인
DELETE /api/auth/session      # 로그아웃
POST   /api/auth/register     # 회원가입
POST   /api/auth/refresh      # 토큰 갱신
```

#### category_controller.py
매장 조회

```python
GET /api/categories/                      # 메인 화면 매장 목록
GET /api/categories/today-recommendations # 오늘의 추천
GET /api/categories/{category_id}         # 매장 상세
```

#### user_controller.py
사용자 정보 관리

```python
PUT    /api/users/me/{field}  # 프로필 수정
DELETE /api/users/me          # 계정 삭제
```

#### like_controller.py
찜 기능

```python
GET    /api/users/me/likes    # 찜 목록 조회
POST   /api/users/me/likes    # 찜 추가
DELETE /api/users/me/likes    # 찜 삭제
```

#### history_controller.py
일정표 히스토리

```python
GET /api/users/me/histories                        # 히스토리 목록
GET /api/users/me/histories/post                   # 리뷰 작성용 (10개 제한)
GET /api/users/me/histories/detail/{merge_id}      # 히스토리 상세
GET /api/users/me/histories/visit-count/{cat_id}   # 방문 횟수
```

#### review_controller.py
리뷰 관리

```python
GET    /api/users/me/reviews/reviewable     # 리뷰 작성 가능한 매장
GET    /api/users/me/reviews                # 내 리뷰 목록
GET    /api/users/me/reviews/count/{cat_id} # 특정 매장 리뷰 개수
POST   /api/users/me/reviews                # 리뷰 작성
DELETE /api/users/me/reviews/{review_id}    # 리뷰 삭제
```

#### service_controller.py
AI 채팅 서비스

```python
POST /api/service/start         # 채팅 세션 시작
POST /api/service/chat          # 메시지 전송
POST /api/service/cal-route     # 경로 계산
POST /api/service/histories     # 일정표 저장
```

### Admin

#### dashboard_controller.py
대시보드 통계 (20+ API)

```python
# HTML 페이지
GET /dashboard.html
GET /data.html
GET /users.html

# 통계 API
GET /api/dashboard/total-users
GET /api/dashboard/recommendation-stats
GET /api/dashboard/popular-categories
# ... 등 20개 이상
```

#### monitoring_controller.py
모니터링 및 제재

```python
GET  /admin/monitoring          # 모니터링 페이지
POST /admin/sanctions           # 사용자 제재
```

## 설계 패턴

### 1. 컨트롤러 구조

```python
from fastapi import APIRouter, Depends
from src.service.user.user_service import UserService
from src.service.auth.jwt import get_jwt_user_id

router = APIRouter(prefix="/api/users")
service = UserService()

@router.get("/me")
async def get_my_info(user_id: str = Depends(get_jwt_user_id)):
    return await service.get_user_info(user_id)
```

### 2. 인증 처리

```python
# JWT 토큰에서 user_id 추출
@router.get("/protected")
async def protected_route(user_id: str = Depends(get_jwt_user_id)):
    # user_id 자동 검증 및 추출
    pass
```

### 3. DTO 사용

```python
from src.domain.dto.user.user_auth_dto import RequestLoginDTO

@router.post("/login")
async def login(dto: RequestLoginDTO):
    # FastAPI가 자동으로 검증
    return await service.login(dto.id, dto.password)
```

### 4. 에러 처리

```python
from fastapi import HTTPException

@router.get("/item/{item_id}")
async def get_item(item_id: str):
    item = await service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

## 응답 형식

### 성공 응답

```python
# 직접 DTO 반환
return ResponseLoginDTO(
    message="success",
    token1="...",
    token2="..."
)

# JSONResponse 사용
return JSONResponse(
    status_code=200,
    content={"status": "success"}
)
```

### 에러 응답

```python
# HTTPException 사용
raise HTTPException(
    status_code=404,
    detail="세션을 찾을 수 없습니다."
)

# 커스텀 예외 사용
raise MissingTokenException()  # 자동으로 HTTP 응답으로 변환됨
```

## 미들웨어

main.py에서 전역 설정:

```python
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 예외 처리
setup_exception_handlers(app)
```

## 라우터 등록

main.py에서 라우터 등록:

```python
app.include_router(auth_controller.router)
app.include_router(category_controller.router)
app.include_router(user_controller.router)
# ... 기타 라우터
```

## 주의사항

### 1. 인증 필요 여부

```python
# 인증 필요
@router.get("/protected")
async def protected(user_id: str = Depends(get_jwt_user_id)):
    pass

# 인증 불필요
@router.post("/public")
async def public():
    pass
```

### 2. Path Parameters vs Query Parameters

```python
# Path Parameter (필수)
@router.get("/users/{user_id}")
async def get_user(user_id: str):
    pass

# Query Parameter (선택)
@router.get("/users")
async def list_users(limit: int = 10, offset: int = 0):
    pass
```

### 3. Request Body

```python
# POST/PUT/PATCH에서만 사용
@router.post("/items")
async def create_item(dto: RequestCreateItemDTO):
    pass

# GET/DELETE에서는 사용 불가
@router.get("/items")
async def list_items(dto: RequestListDTO):  # 오류!
    pass
```