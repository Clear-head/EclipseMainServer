# Utils

유틸리티 함수 및 공통 모듈 모음입니다.

## 구조

```
utils/
├── path.py                      # 경로 관리
├── make_address.py              # 주소 포맷팅
├── crawlers_loader.py           # 크롤링 설정 로더
└── exception_handler/           # 예외 처리
    ├── http_log_handler.py      # HTTP 예외 핸들러
    └── auth_error_class.py      # 인증 예외 클래스
```

## 주요 모듈

### path.py

프로젝트 내 설정 파일 경로를 중앙 관리합니다.

```python
from src.utils.path import path_dic

# 사용 가능한 경로
path_dic = {
    "database_config": "src/resources/config/database_config.json",
    "log_config": "src/resources/config/log_config.json",
    "env": "src/resources/config/.env",
    "redis_config": "src/resources/config/redis_config.json"
}
```

사용 예시:

```python
from src.utils.path import path_dic
import json

with open(path_dic["database_config"]) as f:
    config = json.load(f)
```

특징:
- 상대 경로 문제 해결
- 설정 파일 경로 일관성 유지
- 경로 변경 시 한 곳만 수정

### make_address.py

주소 문자열을 생성하는 유틸리티입니다.

```python
from src.utils.make_address import add_address

address = add_address(
    do="서울특별시",
    si="",
    gu="강남구",
    detail="역삼동 123-45"
)
# "서울특별시 강남구 역삼동 123-45"
```

함수:

```python
def add_address(do: str, si: str, gu: str, detail: str) -> str
```

특징:
- 빈 문자열 자동 제거
- 공백으로 구분
- None 처리

### crawlers_loader.py

크롤링 설정 파일을 로드합니다.

```python
from src.utils.crawlers_loader import load_json_resource

# src/resources/crawl/naver_config.json 로드
config = load_json_resource("naver_config.json")
```

함수:

```python
def load_json_resource(filename: str) -> Dict[str, Any]
```

특징:
- src/resources/crawl/ 디렉토리에서 파일 로드
- JSON 파싱 오류 처리
- 파일 없을 시 빈 dict 반환
- 로깅 포함

## Exception Handler

### http_log_handler.py

FastAPI 전역 예외 핸들러를 설정합니다.

```python
from src.utils.exception_handler.http_log_handler import setup_exception_handlers

app = FastAPI()
setup_exception_handlers(app)
```

처리하는 예외:

1. **MissingTokenException**: 401 Unauthorized
2. **ExpiredAccessTokenException**: 401 Unauthorized
3. **InvalidTokenException**: 401 Unauthorized
4. **UserBannedException**: 403 Forbidden
5. **InvalidCredentialsException**: 401 Unauthorized
6. **UserAlreadyExistsException**: 409 Conflict
7. **DuplicateUserInfoError**: 409 Conflict

응답 형식:

```json
{
  "detail": "에러 메시지"
}
```

예시:

```python
@app.exception_handler(MissingTokenException)
async def missing_token_handler(request, exc):
    return JSONResponse(
        status_code=401,
        content={"detail": "토큰이 제공되지 않았습니다."}
    )
```

### auth_error_class.py

인증 관련 커스텀 예외 클래스들입니다.

```python
from src.utils.exception_handler.auth_error_class import (
    MissingTokenException,
    ExpiredAccessTokenException,
    InvalidTokenException,
    UserBannedException,
    InvalidCredentialsException,
    UserAlreadyExistsException,
    DuplicateUserInfoError
)
```

예외 클래스:

#### MissingTokenException
```python
raise MissingTokenException()
# 401: "토큰이 제공되지 않았습니다."
```

#### ExpiredAccessTokenException
```python
raise ExpiredAccessTokenException()
# 401: "Access Token이 만료되었습니다. 토큰을 갱신하세요."
```

#### InvalidTokenException
```python
raise InvalidTokenException()
# 401: "유효하지 않은 토큰입니다."
```

#### UserBannedException
```python
raise UserBannedException(banned_until=datetime.now())
# 403: "계정이 정지되었습니다. 해제 일시: {날짜}"
```

#### InvalidCredentialsException
```python
raise InvalidCredentialsException()
# 401: "아이디 또는 비밀번호가 올바르지 않습니다."
```

#### UserAlreadyExistsException
```python
raise UserAlreadyExistsException()
# 409: "이미 존재하는 사용자입니다."
```

#### DuplicateUserInfoError
```python
raise DuplicateUserInfoError()
# 409: "중복된 사용자 정보가 있습니다."
```

사용 예시:

```python
# 서비스 레이어에서
async def login(id: str, password: str):
    user = await repo.select(id=id)
    
    if not user:
        raise InvalidCredentialsException()
    
    if not verify_password(password, user.password):
        raise InvalidCredentialsException()
    
    # 블랙리스트 확인
    banned = await black_repo.select(id=id)
    if banned:
        raise UserBannedException(banned[0].banned_until)
    
    return create_tokens(user)
```

## 사용 패턴

### 1. 경로 관리

```python
# 잘못된 방법
with open("../../resources/config/db.json") as f:
    config = json.load(f)

# 올바른 방법
from src.utils.path import path_dic

with open(path_dic["database_config"]) as f:
    config = json.load(f)
```

### 2. 예외 처리

```python
# 서비스에서 예외 발생
from src.utils.exception_handler.auth_error_class import MissingTokenException

if not token:
    raise MissingTokenException()

# FastAPI가 자동으로 처리
# → 401 응답 with {"detail": "토큰이 제공되지 않았습니다."}
```

### 3. 설정 로드

```python
# 크롤링 설정
from src.utils.crawlers_loader import load_json_resource

config = load_json_resource("naver_config.json")
if not config:
    logger.warning("기본 설정 사용")
    config = DEFAULT_CONFIG
```

## 확장 가이드

### 새로운 예외 추가

1. `auth_error_class.py`에 클래스 추가:

```python
class MyCustomException(Exception):
    def __init__(self, message: str = "커스텀 에러"):
        self.message = message
        super().__init__(self.message)
```

2. `http_log_handler.py`에 핸들러 추가:

```python
@app.exception_handler(MyCustomException)
async def my_custom_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message}
    )
```

### 새로운 유틸리티 추가

```python
# src/utils/my_util.py
def my_utility_function():
    """유틸리티 함수 설명"""
    pass

# 사용
from src.utils.my_util import my_utility_function
```

## 모범 사례

### 1. 에러 메시지는 명확하게

```python
# 나쁜 예
raise Exception("Error")

# 좋은 예
raise InvalidCredentialsException()  # 명확한 예외 클래스
```

### 2. 경로는 path_dic 사용

```python
# 나쁜 예
CONFIG_PATH = "../config/db.json"

# 좋은 예
from src.utils.path import path_dic
CONFIG_PATH = path_dic["database_config"]
```

### 3. 설정 파일은 로더 사용

```python
# 나쁜 예
with open("config.json") as f:
    config = json.load(f)  # 에러 처리 없음

# 좋은 예
config = load_json_resource("config.json")  # 에러 처리 포함
```

## 주의사항

### 1. 순환 참조

utils는 다른 모듈에서 import하므로, utils에서 다른 모듈을 import하면 순환 참조 발생 가능

```python
# utils에서는 최소한의 import만
from pathlib import Path  # OK
from src.service.user_service import UserService  # 피하기
```

### 2. 전역 변수

path_dic 같은 전역 변수는 불변으로 유지

```python
# 나쁜 예
path_dic["new_key"] = "new_value"  # 수정하지 말 것

# 좋은 예
# 필요하면 path.py 파일 자체를 수정
```

### 3. 예외 클래스 상속
```
class MyException(Exception):
    pass
```

## 테스트

### 예외 핸들러 테스트

```python
from fastapi.testclient import TestClient

def test_missing_token():
    response = client.get("/protected")
    assert response.status_code == 401
    assert "토큰이 제공되지 않았습니다" in response.json()["detail"]
```

### 유틸리티 함수 테스트

```python
def test_add_address():
    result = add_address("서울", "", "강남구", "역삼동")
    assert result == "서울 강남구 역삼동"
```