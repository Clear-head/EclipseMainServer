# Logger

프로젝트 전체의 로깅을 관리하는 모듈입니다.

## 구조

```
logger/
└── custom_logger.py    # 커스텀 로거 설정
```

## custom_logger.py

프로세스별 로거를 생성하고 관리합니다.

### 주요 기능

#### get_logger()

프로세스별 로거 인스턴스를 반환합니다.

```python
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)
logger.info("로그 메시지")
```

### 로거 특징

#### 1. 프로세스별 분리

```python
# src/service/user/user_service.py
logger = get_logger(__name__)
# → 로거 이름: "src"
# → 로그 파일: logs/src/src-2024-11-18.txt
```

#### 2. 일자별 파일

로그 파일은 날짜별로 자동 생성됩니다.

```
logs/
└── src/
    ├── src-2024-11-18.txt
    ├── src-2024-11-19.txt
    └── src-2024-11-20.txt
```

#### 3. 자동 디렉토리 생성

로그 디렉토리가 없으면 자동으로 생성됩니다.

#### 4. 캐싱

동일한 로거는 캐시에서 재사용됩니다.

```python
# 첫 호출: 새 로거 생성
logger1 = get_logger("module1")

# 두 번째 호출: 캐시에서 반환
logger2 = get_logger("module1")

assert logger1 is logger2  # True
```

## 설정 파일

### log_config.json

로그 설정은 `src/resources/config/log_config.json`에서 관리됩니다.

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "default": {
      "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "level": "INFO",
      "formatter": "default",
      "stream": "ext://sys.stdout"
    },
    "file": {
      "class": "logging.FileHandler",
      "level": "DEBUG",
      "formatter": "default",
      "filename": "app.log",
      "mode": "a",
      "encoding": "utf-8"
    }
  },
  "root": {
    "level": "DEBUG",
    "handlers": ["console", "file"]
  }
}
```

### 설정 항목

#### formatters

로그 메시지 형식 정의

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

예시:
```
2024-11-18 10:30:45,123 - src - INFO - 사용자 로그인 성공
```

#### handlers

로그 출력 대상

1. console: 콘솔 출력
2. file: 파일 저장

#### level

로그 레벨 (낮은 순서):
- DEBUG: 디버그 정보
- INFO: 일반 정보
- WARNING: 경고
- ERROR: 에러
- CRITICAL: 치명적 오류

## 사용 방법

### 기본 사용

```python
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)

# 로그 레벨별 사용
logger.debug("디버그 메시지")
logger.info("정보 메시지")
logger.warning("경고 메시지")
logger.error("에러 메시지")
logger.critical("치명적 오류 메시지")
```

### 예외 로깅

```python
try:
    result = some_function()
except Exception as e:
    logger.error(f"함수 실행 실패: {e}")
    logger.error(f"상세 정보", exc_info=True)  # 스택 트레이스 포함
    raise
```

### 포맷팅

```python
# f-string 사용
user_id = "user123"
logger.info(f"사용자 {user_id} 로그인 성공")

# 변수 직접 전달
logger.info("사용자 %s 로그인 성공", user_id)
```

### 조건부 로깅

```python
# DEBUG 레벨은 개발 환경에서만
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"복잡한 데이터: {expensive_operation()}")
```

## 실제 사용 예시

### Service Layer

```python
from src.logger.custom_logger import get_logger

class UserService:
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def login(self, id: str, password: str):
        self.logger.info(f"로그인 시도: {id}")
        
        try:
            user = await self.repo.select(id=id)
            
            if not user:
                self.logger.warning(f"존재하지 않는 사용자: {id}")
                raise InvalidCredentialsException()
            
            if not verify_password(password, user.password):
                self.logger.warning(f"비밀번호 불일치: {id}")
                raise InvalidCredentialsException()
            
            self.logger.info(f"로그인 성공: {id}")
            return create_tokens(user)
            
        except Exception as e:
            self.logger.error(f"로그인 실패: {id}, 오류: {e}")
            raise
```

### Repository Layer

```python
from src.logger.custom_logger import get_logger

class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        self.table = users_table
    
    async def insert(self, item):
        self.logger.debug(f"사용자 삽입 시도: {item.id}")
        
        try:
            result = await super().insert(item)
            self.logger.info(f"사용자 삽입 성공: {item.id}")
            return result
        except IntegrityError as e:
            self.logger.error(f"중복 사용자 ID: {item.id}")
            raise
        except Exception as e:
            self.logger.error(f"사용자 삽입 실패: {e}", exc_info=True)
            raise
```

### Controller Layer

```python
from src.logger.custom_logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.post("/login")
async def login(dto: RequestLoginDTO):
    logger.info(f"로그인 API 호출: {dto.id}")
    
    try:
        result = await user_service.login(dto.id, dto.password)
        return result
    except InvalidCredentialsException:
        logger.warning(f"로그인 실패: {dto.id}")
        raise
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}", exc_info=True)
        raise
```

## 로그 레벨 선택 가이드

### DEBUG
- 개발/디버깅 시 사용
- 변수 값, 중간 단계 정보
- 프로덕션에서는 비활성화

```python
logger.debug(f"쿼리 실행: {sql}")
logger.debug(f"응답 데이터: {response}")
```

### INFO
- 정상적인 동작 흐름
- 주요 이벤트 기록
- 프로덕션에서도 활성화

```python
logger.info(f"사용자 로그인: {user_id}")
logger.info(f"크롤링 시작: {url}")
logger.info(f"배치 처리 완료: {count}개")
```

### WARNING
- 예상 가능한 문제
- 에러는 아니지만 주의 필요
- 복구 가능한 상황

```python
logger.warning(f"존재하지 않는 사용자 조회: {user_id}")
logger.warning(f"API 응답 지연: {duration}ms")
logger.warning(f"캐시 미스: {key}")
```

### ERROR
- 실제 에러 발생
- 기능 실패
- 즉시 확인 필요

```python
logger.error(f"DB 연결 실패: {e}")
logger.error(f"외부 API 오류: {e}")
logger.error(f"데이터 검증 실패: {e}")
```

### CRITICAL
- 시스템 전체에 영향
- 서비스 중단 수준
- 긴급 대응 필요

```python
logger.critical(f"DB 서버 다운")
logger.critical(f"메모리 부족")
logger.critical(f"디스크 용량 초과")
```

## 모범 사례

### 1. 모듈 시작 시 로거 생성

```python
# 파일 상단에
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)

# 클래스 내부에서
class MyService:
    def __init__(self):
        self.logger = get_logger(__name__)
```

### 2. 의미 있는 메시지

```python
# 나쁜 예
logger.info("성공")

# 좋은 예
logger.info(f"사용자 {user_id} 프로필 업데이트 성공")
```

### 3. 민감 정보 제외

```python
# 나쁜 예
logger.info(f"비밀번호: {password}")

# 좋은 예
logger.info(f"사용자 인증 성공: {user_id}")
```

### 4. 예외 시 스택 트레이스

```python
try:
    result = operation()
except Exception as e:
    logger.error(f"작업 실패: {e}", exc_info=True)  # 스택 트레이스 포함
    raise
```

### 5. 성능 고려

```python
# 나쁜 예
logger.debug(f"데이터: {expensive_serialization()}")

# 좋은 예
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"데이터: {expensive_serialization()}")
```

## 로그 분석

### 로그 파일 위치

```
logs/
└── src/
    └── src-2024-11-18.txt
```

### 로그 검색

```bash
# 특정 사용자 로그 검색
grep "user123" logs/src/src-2024-11-18.txt

# 에러 로그만 검색
grep "ERROR" logs/src/src-2024-11-18.txt

# 특정 시간대 로그
grep "2024-11-18 10:" logs/src/src-2024-11-18.txt
```

### 로그 모니터링

```bash
# 실시간 로그 확인
tail -f logs/src/src-2024-11-18.txt

# 에러 로그 실시간 확인
tail -f logs/src/src-2024-11-18.txt | grep ERROR
```

## 프로덕션 설정

### 레벨 조정

프로덕션에서는 INFO 이상만 기록:

```json
{
  "handlers": {
    "file": {
      "level": "INFO"  # DEBUG 제외
    }
  }
}
```

### 로그 로테이션

오래된 로그 파일 자동 삭제:

```python
# 별도 스크립트로 구현
import os
from datetime import datetime, timedelta

def cleanup_old_logs(days=30):
    cutoff = datetime.now() - timedelta(days=days)
    for file in os.listdir("logs/src"):
        if file_date < cutoff:
            os.remove(file)
```

## 주의사항

### 1. 과도한 로깅 피하기

```python
# 나쁜 예 (루프 내 로깅)
for item in items:
    logger.info(f"처리 중: {item}")  # 수천 개면 로그 폭주

# 좋은 예
logger.info(f"총 {len(items)}개 항목 처리 시작")
for item in items:
    process(item)
logger.info(f"처리 완료")
```

### 2. 순환 참조 주의

로거에서 다른 모듈을 import하지 말 것

### 3. 파일 핸들 관리

get_logger()를 반복 호출해도 문제없음 (캐싱됨)