# EclipseMainServer



# API 명세서

## 목차
- [1. 인증 (Authentication)](#1-인증-authentication)
- [2. 카테고리 (Categories)](#2-카테고리-categories)
- [3. 사용자 정보 (User Info)](#3-사용자-정보-user-info)
- [4. AI 서비스 (Service)](#4-ai-서비스-service)
- [5. 사용자 관리 (User Management)](#5-사용자-관리-user-management)

---

## 1. 인증 (Authentication)

### 1.1 로그인
**POST** `/api/auth/session`


#### Request Body
```json
{
  "id": "user123",
  "password": "password123"
}
```

#### Response (200 OK)
```json
{
  "message": "success",
  "token1": "access_token_string",
  "token2": "refresh_token_string",
  "info": {
    "username": "홍길동",
    "nickname": "길동이",
    "birth": "1990-01-01T00:00:00",
    "phone": "010-1234-5678",
    "email": "user@example.com",
    "address": "서울시 강남구"
  }
}
```

#### Error Responses
- **400**: 잘못된 자격 증명
- **409**: 중복된 사용자 정보

---

### 1.2 로그아웃
**DELETE** `/api/auth/session`

---

### 1.3 회원가입
**POST** `/api/auth/register`
#### Request Body
```json
{
  "id": "user123",
  "username": "홍길동",
  "password": "password123",
  "nickname": "길동이",
  "birth": "1990-01-01T00:00:00",
  "phone": "010-1234-5678",
  "email": "user@example.com",
  "sex": 1,
  "address": "서울시 강남구"
}
```

#### Response (200 OK)
```json
{
  "message": "success"
}
```

#### Error Responses
- **409**: 이미 존재하는 사용자

---

### 1.4 JWT 토큰 갱신
**POST** `/api/auth/refresh`

Refresh Token을 사용하여 새로운 Access Token을 발급

#### Request Body
```json
{
  "token": "refresh_token_string",
  "id": "user123"
}
```

#### Response (200 OK)
```json
{
  "token": "new_access_token_string"
}
```

#### Error Responses
- **400**: 토큰 누락
- **401**: 만료된 Refresh Token

---

### 1.5 아이디 찾기
**POST** `/api/auth/id`


---

### 1.6 비밀번호 찾기
**POST** `/api/auth/password`


---

## 2. 카테고리 (Categories)

### 2.1 메인 화면 카테고리 조회
**GET** `/api/categories/`

메인 화면에 표시할 카테고리 목록을 조회합니다.

#### Headers
- `Authorization`: Bearer {access_token}

#### Response (200 OK)
```json
{
  "categories": [
    {
      "id": "cat_001",
      "title": "맛있는 카페",
      "image_url": "https://example.com/image.jpg",
      "detail_address": "서울특별시 강남구 역삼동 123",
      "sub_category": "카페"
    }
  ]
}
```

---

### 2.2 카테고리 상세 조회
**GET** `/api/categories/{category_id}`

특정 매장의 상세 정보 조회

#### Headers
- `Authorization`: Bearer {access_token}

#### Path Parameters
- `category_id`: 카테고리 ID

#### Response (200 OK)
```json
{
  "is_like": true,
  "tags": ["조용한", "인테리어", "커피"],
  "reviews": [
    {
      "nickname": "사용자1",
      "star": 5,
      "comment": "정말 좋아요!"
    }
  ]
}
```

#### Error Responses
- **404**: 카테고리를 찾을 수 없음

---

## 3. 사용자 정보 (User Info)

### 3.1 좋아요 목록 조회
**GET** `/api/users/me/likes`

사용자가 좋아요한 매장 목록 조회

#### Headers
- `Authorization`: Bearer {access_token}

#### Response (200 OK)
```json
{
  "like_list": [
    {
      "type": "카페",
      "category_id": "cat_001",
      "category_name": "맛있는 카페",
      "category_image": "https://example.com/image.jpg",
      "sub_category": "카페",
      "do": "서울특별시",
      "si": null,
      "gu": "강남구",
      "detail_address": "역삼동 123",
      "category_address": "서울특별시강남구역삼동 123"
    }
  ]
}
```

---

### 3.2 좋아요 설정
**POST** `/api/users/me/likes`

사용자별 좋아요 목록에 추가

#### Headers
- `Authorization`: Bearer {access_token}

#### Request Body
```json
{
  "category_id": "cat_001"
}
```

#### Response (200 OK)
```json
"success"
```

---

### 3.3 좋아요 취소
**DELETE** `/api/users/me/likes`

사용자별 좋아요 취소

#### Headers
- `Authorization`: Bearer {access_token}

#### Request Body
```json
{
  "category_id": "cat_001"
}
```

#### Response (200 OK)
```json
"success"
```

---

### 3.4 리뷰 목록 조회
**GET** `/api/users/me/reviews`

사용자(본인) 리뷰 조회

#### Headers
- `Authorization`: Bearer {access_token}

#### Response (200 OK)
```json
{
  "review_list": [
    {
      "review_id": "rev_001",
      "category_id": "cat_001",
      "category_name": "맛있는 카페",
      "comment": "정말 좋아요!",
      "stars": 5,
      "created_at": "2024-01-01T12:00:00"
    }
  ]
}
```

---

### 3.5 히스토리 목록 조회
**GET** `/api/users/me/histories`

사용자의 방문 히스토리 목록 조회

#### Headers
- `Authorization`: Bearer {access_token}

#### Response (200 OK)
```json
{
  "results": [
    {
      "id": "merge_001",
      "visited_at": "2024-01-01T14:00:00",
      "categories_name": "카페레스토랑"
    }
  ]
}
```

---

### 3.6 히스토리 상세 조회
**GET** `/api/users/me/histories/detail/{merge_history_id}`

특정 히스토리의 상세 정보 조회(일정표 보기)

#### Headers
- `Authorization`: Bearer {access_token}

#### Path Parameters
- `merge_history_id`: 병합 히스토리 ID

#### Response (200 OK)
```json
{
  "categories": [
    {
      "duration": 60,
      "transportation_type": "도보",
      "category_id": 1,
      "category_name": "맛있는 카페"
    }
  ]
}
```

---

## 4. AI 서비스 (Service)

### 4.1 대화 시작
**POST** `/api/service/start`

AI와의 대화를 시작

#### Headers
- `Authorization`: Bearer {access_token}

#### Request Body
```json
{
  "play_address": "서울시 강남구",
  "peopleCount": 2,
  "selectedCategories": ["카페", "음식점"]
}
```

#### Response (200 OK)
```json
{
  "status": "success",
  "sessionId": "user_session_id",
  "message": "2명이서 카페, 음식점을(를) 즐기시는군요! 먼저 카페에 대해 물어볼게요.",
  "stage": "collecting_details",
  "progress": {
    "current": 0,
    "total": 2
  }
}
```

---

### 4.2 채팅 메시지 전송
**POST** `/api/service/chat`

AI에게 메시지를 전송

#### Headers
- `Authorization`: Bearer {access_token}

#### Request Body
```json
{
  "message": "조용하고 커피가 맛있는 곳"
}
```

#### Response (200 OK) - 태그 수집 단계
```json
{
  "status": "success",
  "message": "현재까지 수집된 키워드: 조용한, 커피",
  "stage": "collecting_details",
  "tags": ["조용한", "커피"],
  "progress": {
    "current": 0,
    "total": 2
  },
  "showYesNoButtons": true,
  "yesNoQuestion": "이 정보로 다음 질문으로 넘어가시겠습니까?",
  "currentCategory": "카페"
}
```

#### Response (200 OK) - 완료 단계
```json
{
  "status": "success",
  "message": "추천 결과를 생성했습니다!",
  "stage": "completed",
  "recommendations": {
    "카페": [
      {
        "id": "cat_001",
        "title": "조용한 카페",
        "image_url": "https://example.com/image.jpg",
        "detail_address": "서울특별시 강남구 역삼동 123",
        "sub_category": "카페"
      }
    ]
  },
  "collectedData": [
    {
      "category": "카페",
      "keywords": ["조용한", "커피"]
    }
  ]
}
```

#### Error Responses
- **404**: 세션을 찾을 수 없음

---

### 4.3 히스토리 저장
**POST** `/api/service/histories`

하루와 대화 결과물 (일정표) 저장

#### Headers
- `Authorization`: Bearer {access_token}

#### Request Body
```json
{
  "template_type": "date",
  "category": [
    {
      "category_id": "cat_001",
      "category_name": "맛있는 카페",
      "duration": 60,
      "transportation": "도보"
    }
  ]
}
```

#### Response (200 OK)
```json
"success"
```

---

## 5. 사용자 관리 (User Management)

### 5.1 사용자 정보 수정
**PUT** `/api/users/me/{field}`

사용자 정보 수정 (닉네임, 비밀번호, 이메일, 주소, 전화번호)

#### Headers
- `Authorization`: Bearer {access_token}

#### Path Parameters
- `field`: 수정할 필드 (nickname, password, email, address, phone)

#### Request Body
```json
{
  "change_field": "새로운값",
  "password": "현재비밀번호"
}
```

#### Response (200 OK)
```json
{
  "msg": "새로운값"
}
```

#### Error Responses
- **404**: 사용자를 찾을 수 없음
- **409**: 중복된 사용자 정보

---

### 5.2 회원 탈퇴
**DELETE** `/api/users/me`

#### Headers
- `Authorization`: Bearer {access_token}

#### Request Body
```json
{
  "password": "current_password"
}
```

#### Response (200 OK)
```json
{
  "status": "success"
}
```

#### Error Responses
- **404**: 사용자를 찾을 수 없음
- **409**: 중복된 사용자 정보

---

## 공통 에러 응답

### 401 Unauthorized
```json
{
  "detail": "인증되지 않은 사용자"
}
```

### 500 Internal Server Error
```json
{
  "detail": "서버 내부 오류"
}
```

---

## 인증

로그인 이후 모든 요청에 jwt 포함, 헤더에 있음

```
Authorization: Bearer {access_token}
```

Access Token이 만료된 경우, `/api/auth/refresh` 에서 새로운 토큰 발급\

---

## 변경 이력

### 버전 1.0
- 초기 API 명세서 작성
- 인증, 카테고리, 사용자 정보, AI 서비스, 사용자 관리 API 정의
