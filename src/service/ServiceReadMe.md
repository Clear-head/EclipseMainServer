# Services

    .

##  

```
service/
 auth/                    # /
    jwt.py              # JWT  /
    password_hash.py    #  
 user/                    #   
    user_service.py     #  CRUD
    like_service.py     #  
    history_service.py  #  
    reviews_service.py  #  
 category/                # () 
    category_service.py #  /
 application/             # AI  
    conversation_handler.py      #   
    recommendation_handler.py    #  
    route_calculation_service.py #  
    tag_handler.py              #  
    utils.py                    # 
 crawl/                   # 
    crawling_naver_list.py      #    
    crawling_naver_one.py       #    
    crawling_kakao.py           #  
    insert_crawled.py           #   
    delete_crawled.py           #   
 chromadb/                #  DB
    store_chromadb_loader.py    # ChromaDB  
 suggest/                 #  
    store_suggest_service.py    #   
 dashboard/               #  
    dashboard_service.py        # / 
    dashboard_data_service.py   #  
    dashboard_users_service.py  #  
 scheduler/               # 
    crawling_scheduler.py       #  
 sanctions/               #  
     sanction_service.py         #  
```

##   

### 1. Auth (/)

#### jwt.py
JWT  ,    ID 

** :**
```python
async def create_jwt_token(user_id: str) -> tuple
    # Access Token Refresh Token 
    # Redis  
    # : (access_token, refresh_token)

async def get_jwt_user_id(jwt: str = Header(None)) -> str
    # JWT user_id 
    #   (,  )
    # Redis  

async def validate_jwt_token(jwt: str) -> bool
    #    ( )
```

**:**
- Access Token: 1 
- Refresh Token: 15 
- Redis   
- HS256  

---

### 2. User Services

#### user_service.py
   (CRUD)

** :**
```python
async def login(id: str, password: str) -> ResponseLoginDTO
    # 1.  
    # 2.  
    # 3.  
    # 4. JWT  

async def register(dto: RequestRegisterDTO) -> ResponseRegisterDTO
    # 1. ID  
    # 2.  
    # 3.  

async def change_info(dto, field: str, user_id: str)
    #    (,  )

async def delete_account(user_id: str, dto, jwt: str)
    # 1.  
    # 2.  
```

#### like_service.py
 

```python
async def set_my_like(data, type: bool, user_id: str) -> str
    # type=True:  
    # type=False:  

async def get_user_like(user_id) -> ResponseLikeListDTO
    # 1.   
    # 2.     (  )
```

#### history_service.py
  

```python
async def get_user_history_list(user_id, limit)
    #    ()

async def get_user_history_detail(user_id, merge_history_id)
    #    (  )

async def get_category_visit_count(user_id, category_id)
    #    

async def get_reviewable_stores(user_id, limit)
    #     ( >  )
```

#### reviews_service.py
 

```python
async def get_user_reviews(user_id)
    #    

async def set_user_review(user_id, dto)
    #  

async def delete_user_review(user_id, review_id)
    #  

async def get_user_review_count(user_id, category_id)
    #     
```

---

### 3. Category Service

#### category_service.py (MainScreenService)
   

```python
async def to_main(limit: int = 10) -> ResponseCategoryListDTO
    #    
    # 1.       
    # 2.   

async def get_category_detail(category_id, user_id)
    # 1.    
    # 2.   
    # 3.   
    # 4.   
```

---

### 4. Application (AI  )

#### conversation_handler.py
AI    

** :**
```python
def handle_user_message(session: Dict, user_message: str)
    # 1.    (//)
    # 2. LLM  
    # 3.   

async def handle_user_action_response(session: Dict, user_response: str)
    #    (Next/More/Yes)

async def handle_results_confirmation(session: Dict, is_confirmed: bool)
    #       

async def save_selected_template(dto, merge_id, user_id)
    #  
```

**  (stage):**
- `collecting_details`:   
- `confirming_random`:   
- `confirming_results`:  
- `completed`: 

#### recommendation_handler.py
  

```python
async def get_store_recommendations(session: Dict)
    # 1.  , ,  
    # 2.   
    #    - : DB  
    #    - : ChromaDB  + GPT 
    # 3.  

async def get_filtered_recommendations(...)
    # 1. ChromaDB  (15)
    # 2.    
    # 3. GPT  (10)

async def get_random_recommendations(...)
    # DB   (10)
```

** :**
```python
RECOMMENDATION_CONFIG = {
    "chromadb_results": 15,      # ChromaDB  
    "gpt_max_results": 10,       # GPT   
    "random_results": 10,        #   
    "min_similarity": 0.2,       #  
    "rerank_multiplier": 5,      #  
}
```

#### route_calculation_service.py
  

```python
async def calculate_route_by_transport_type(transport_type, origin, destination)
    # transport_type:
    #   0:  ( API)
    #   1:  (T API)
    #   2:  ( API)

async def _calculate_walking_route(...)
    #   

async def _calculate_public_transit(...)
    # T   (  )

async def _calculate_car_route(...)
    #   
```

#### tag_handler.py
   

```python
def collect_tags_from_message(session, user_message, category, people_count)
    # 1. GPT  
    # 2.   
    # 3.  

def handle_tag_action(session, user_response, ...)
    #  /  
    # : "#", "#"
```

---

### 5. Crawl ()

#### crawling_naver_list.py
    

**:**
- Playwright 
-    (30)
-   ( )
-  

** :**
```python
class NaverMapFavoriteCrawler:
    async def crawl_favorite_list(favorite_url, delay)
        # 1.   
        # 2.   
        # 3.   
```

#### crawling_naver_one.py
    

```python
class NaverStoreCrawler:
    async def crawl_single_store(store_url)
        # 1.   
        # 2.    
        # 3.  
```

#### insert_crawled.py / delete_crawled.py
  CRUD

---

### 6. ChromaDB

#### store_chromadb_loader.py
 DB  

**:**
- GPU  (CUDA)
- intfloat/multilingual-e5-large  
-    

**  :**
1.  (3 )
2.  (2 )
3.  (2 , 2~11)
4.  ( )

```python
class StoreChromaDBLoader:
    async def load_all_stores(batch_size=100)
        # 1.   
        # 2.   
        # 3.   
        # 4.    
```

---

### 7. Suggest

#### store_suggest_service.py
  

```python
class StoreSuggestService:
    async def suggest_stores(personnel, region, category_type, user_keyword, ...)
        # 1. ChromaDB 
        # 2.   (, )
        # 3.  (, , rerank)
        # 4.  

    async def get_store_details(store_ids)
        #     (  )

    async def get_random_stores_from_db(region, category_type, n_results)
        # DB  
```

---

### 8. Dashboard

#### dashboard_service.py
  - /

```python
async def get_tag_statistics(category_type)
    #   

async def get_popular_places()
    #   

async def get_district_stats()
    #   
```

#### dashboard_data_service.py
  - 

```python
async def get_total_users()
    #   

async def get_recommendation_stats()
    #    

async def get_weekly_average_stats()
    #   

async def get_popular_categories()
    #  

async def get_template_stats()
    #   

async def get_transportation_stats()
    #  
```

#### dashboard_users_service.py
  - 

```python
async def get_delete_cause_stats()
    #   

async def get_general_inquiries()
    #  

async def get_report_inquiries()
    #  
```

---

### 9. Scheduler

#### crawling_scheduler.py
 

```python
# APScheduler 
#   2   ()
```

---

### 10. Sanctions

#### sanction_service.py
  

```python
async def add_ban_user(dto)
    #  
```

##   

1. ** **:     
2. ** **: Repository  
3. ** **: async/await 
4. ****:    

##   

###  
```python
# 
from src.service.user.like_service import LikeService

service = LikeService()
result = await service.get_user_like(user_id)
```

###  
```python
# Repository   
async def some_service_method(self):
    #  DB 
    await self.repo.insert(entity1)
    await self.repo.update(id, entity2)
    #  /
```
