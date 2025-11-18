# DTO (Data Transfer Objects)

API /       DTO .

##  

```
dto/
 user/                     #  
    user_auth_dto.py      # , , 
    user_profile_dto.py   #  /
    user_account_dto.py   #  
    user_sanctions_dto.py #  
 category/                 # () 
    category_dto.py       #  
    category_detail_dto.py #  
 review/                   #  
    review_dto.py         #  CRUD 
 like/                     #  
    like_dto.py           # 
 history/                  #  
    history_dto.py        #  
 chat/                     # AI 
    chat_session_dto.py
    chat_message_dto.py
    chat_recommendation_dto.py
 transport/
    transport_dto.py
 crawl/
     crawl_category_dto.py
     crawl_tags_dto.py
```

##   DTO 

### 1. User DTOs

#### user_auth_dto.py
```python
RequestLoginDTO          #  
ResponseLoginDTO         #   ( )
RequestRegisterDTO 
ResponseRegisterDTO 
RequestRefreshTokenDTO
```

** :**
```python
# 
login_request = RequestLoginDTO(
    id="user123",
    password="password123"
)

# 
ResponseLoginDTO(
    message="success",
    token1="access_token",
    token2="refresh_token",
    info=UserInfoDTO(...)
)
```

#### user_profile_dto.py
```python
RequestUpdateProfileDTO  #   
ResponseUpdateProfileDTO #   
```

#### user_account_dto.py
```python
RequestDeleteAccountDTO  #   
```

---

### 2. Category DTOs

#### category_dto.py
```python
CategoryListItemDTO      #   
ResponseCategoryListDTO  #   
```

**:**
- `id`:  ID
- `title`: 
- `image_url`:  URL
- `detail_address`:  
- `sub_category`:  
- `lat`, `lng`: 
- `review_count`:  
- `average_stars`:  

#### category_detail_dto.py
```python
ResponseCategoryDetailDTO #   
ReviewItemDTO            #  
TagItemDTO               #  
```

** :**
- `business_hour`: 
- `phone`: 
- `menu`: 
- `is_liked`:  
- `tags`:  
- `reviews`:  

---

### 3. Review DTOs

#### review_dto.py
```python
RequestCreateReviewDTO   #   
ResponseReviewListDTO    #   
ReviewDTO                #  
ResponseDeleteReviewDTO  #   
```

**  :**
```python
RequestCreateReviewDTO(
    category_id="cat123",
    comment="!",
    stars=5
)
```

---

### 4. Like DTOs

#### like_dto.py
```python
RequestToggleLikeDTO     #   
ResponseLikeListDTO      #   
```

** :**
```python
#  /
RequestToggleLikeDTO(
    category_id="cat123"
)
```

---

### 5. History DTOs

#### history_dto.py
```python
ResponseHistoryListDTO    #   
HistoryListItemDTO       #   
ResponseHistoryDetailDTO #   
HistoryDetailItemDTO     #   
RequestSaveHistoryDTO    #   
SaveHistoryItemDTO       #   
```

**  :**
```python
RequestSaveHistoryDTO(
    template_type="0",  # 0: , 1: 
    category=[
        SaveHistoryItemDTO(
            seq=0,
            category_id="cat123",
            category_name="",
            latitude="37.123",
            longitude="127.123",
            transportation="0",
            duration=600,
            distance=1000,
            routes=[]
        )
    ]
)
```

---

### 6. Chat DTOs

#### chat_session_dto.py
```python
RequestStartChatSessionDTO   #    
ResponseStartChatSessionDTO  #    
```

**  :**
```python
RequestStartChatSessionDTO(
    play_address="",
    peopleCount=2,
    selectedCategories=["", ""]
)
```

#### chat_message_dto.py
```python
RequestChatMessageDTO        #   
ResponseChatMessageDTO       #  
```

**  :**
```python
RequestChatMessageDTO(
    message="  "
)

# 
ResponseChatMessageDTO(
    status="success",
    message="   !",
    stage="collecting_details",
    tags=[" "],
    showYesNoButtons=True,
    currentCategory=""
)
```

#### chat_recommendation_dto.py
```python
ResponseChatRecommendationDTO #   
RecommendationItemDTO        #  
CollectedDataItemDTO         #  
```

---

### 7. Transport DTOs

#### transport_dto.py
```python
RequestCalculateTransportDTO  #   
ResponseCalculateTransportDTO #   
PublicTransportRouteDTO      #   
```

**  :**
```python
RequestCalculateTransportDTO(
    transport_type="1",  # 0: , 1: , 2: 
    origin="127.123,37.123",
    destination="127.456,37.456"
)

# 
ResponseCalculateTransportDTO(
    duration=600,        # 
    distance=1000,       # 
    routes=[             #  
        PublicTransportRouteDTO(
            description="2  ",
            duration_min=10
        )
    ]
)
```

---

### 8. Crawl DTOs

#### crawl_category_dto.py
```python
InsertCrawledCategoryDTO  #   
```

#### crawl_tags_dto.py
```python
InsertCrawledTagsDTO      #   
```

##   

### Request DTO
- `Request{}DTO`
- : `RequestLoginDTO`, `RequestCreateReviewDTO`

### Response DTO
- `Response{}DTO`
- : `ResponseLoginDTO`, `ResponseCategoryListDTO`

### Item DTO ( )
- `{}ItemDTO`  `{}DetailDTO`
- : `CategoryListItemDTO`, `HistoryDetailItemDTO`

##   

1. **  **
   - Request:   
   - Response:   
   - Item: Response   

2. ** **
   -    
   - Pydantic   

3. ****
   -  DTO   
   -  DTO  

4. ****
   -   
   -   

##   

### 1. DTO 
Pydantic    .
```python
#    ValidationError 
dto = RequestLoginDTO(
    id=123,  # str 
    password="test"
)
```

### 2. Optional 
```python
from typing import Optional

class MyDTO(BaseModel):
    required_field: str
    optional_field: Optional[str] = None
```

### 3.  DTO
```python
class ItemDTO(BaseModel):
    id: str
    name: str

class ListResponseDTO(BaseModel):
    items: List[ItemDTO]
    total: int
```

### 4.  
```python
class ConfigDTO(BaseModel):
    limit: int = 10
    offset: int = 0
```

