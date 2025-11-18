# Domain

      .

##  

```
domain/
 dto/              # Data Transfer Objects (API /)
 entities/         # Database Entity 
```

##  Entities

  1:1   .

###  

- **CategoryEntity**: () 
- **UserEntity**:  
- **ReviewEntity**:  
- **UserLikeEntity**:  
- **UserHistoryEntity**:  
- **MergeHistoryEntity**:   
- **TagsEntity**:  
- **CategoryTagsEntity**: - 

### 

-   Pydantic BaseModel 
- `from_dto()`  DTO   
-     

##  DTOs

API /    .

###  DTO

#### user/
- **user_auth_dto.py**: , ,  
- **user_profile_dto.py**:  /
- **user_account_dto.py**:  

#### category/
- **category_dto.py**:   
- **category_detail_dto.py**:   

#### review/
- **review_dto.py**:  CRUD 

#### like/
- **like_dto.py**:  //

#### history/
- **history_dto.py**:   

#### chat/
- **chat_session_dto.py**: AI   
- **chat_message_dto.py**:  
- **chat_recommendation_dto.py**: AI  

#### transport/
- **transport_dto.py**:   /

#### crawl/
- **crawl_category_dto.py**:   
- **crawl_tags_dto.py**:   

###  

- Request DTO: `Request{}DTO`
- Response DTO: `Response{}DTO`
-  DTO: `{}ItemDTO`, `{}DetailDTO`

##   

### Entity 
```python
from src.domain.entities.category_entity import CategoryEntity

entity = CategoryEntity(
    id="cat123",
    name=" ",
    type=0,
    latitude=37.123456,
    longitude=127.123456
)
```

### DTO 
```python
from src.domain.dto.user.user_auth_dto import RequestLoginDTO

login_request = RequestLoginDTO(
    id="user123",
    password="password"
)
```

### DTO  Entity 
```python
from src.domain.dto.crawl.crawl_category_dto import InsertCrawledCategoryDTO
from src.domain.entities.category_entity import CategoryEntity

dto = InsertCrawledCategoryDTO(...)
entity = CategoryEntity.from_dto(dto)
```

##   

1. ** **:  DTO/Entity    
2. ****:     
3. ****: Pydantic    
4. ****:    
