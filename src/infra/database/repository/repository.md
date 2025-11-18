# Repository

   Repository .

##  

```
repository/
 base_repository.py              #  CRUD 
 maria_engine.py                 # MariaDB 
 category_repository.py          #
 category_tags_repository.py     #
 tags_repository.py              # 
 user_repository.py              # 
 user_like_repository.py         # 
 user_history_repository.py      #  
 merge_history_repository.py     #  
 reviews_repository.py           # 
 black_repository.py             # 
 statistics_repository.py        #  
```

##  Base Repository

 Repository   .

###  

#### 1. insert
```python
async def insert(self, item) -> bool
```

** :**
```python
entity = UserEntity(
    id="user123",
    username="",
    password="hashed_password"
)

success = await user_repo.insert(entity)
```

---

#### 2. select
```python
async def select(
    self,
    joins=None,          # JOIN 
    columns=None,        #  
    return_dto=None,     #  DTO
    limit=None,          #  
    order=None,          #  
    **filters            #  
) -> list
```

** :**
```python
#  
users = await repo.select(id='user123')

#  
users = await repo.select(age=25, city='Seoul')

# IN  ( )
users = await repo.select(id=['user1', 'user2', 'user3'])
```

** :**
```python
# list  (alias )
users = await repo.select(
    columns=['id', 'nickname'],
    age=25
)

# dict  (alias )
users = await repo.select(
    columns={
        'id': None,           # alias 
        'nickname': 'name',   # 'name' alias
    },
    age=25
)
```

**JOIN :**
```python
reviews = await repo.select(
    joins=[
        {
            'table': user_table,
            'on': {'user_id': 'id'},      # review.user_id = user.id
            'alias': 'user',
            'type': 'left'                # optional, default 'inner'
        }
    ],
    columns={
        'id': None,                       # review.id
        'comment': 'review_comment',      # review.comment as review_comment
        'user.nickname': 'author_name',   # user.nickname as author_name
        'user.email': None                # user.email
    },
    category_id='cat123'
)
```

** JOIN :**
```python
# 3  JOIN
results = await repo.select(
    joins=[
        {
            'table': user_table,
            'on': {'user_id': 'id'},
            'alias': 'user',
            'base_table': 'main'          #   JOIN
        },
        {
            'table': category_table,
            'on': {'category_id': 'id'},
            'alias': 'category',
            'base_table': 'main'
        }
    ],
    columns=[
        'id',
        'user.nickname',
        'category.name'
    ]
)
```

**  :**
```python
# 
users = await repo.select(
    order='created_at',  # 
    limit=10
)

# 
users = await repo.select(
    order='-created_at',  # '-'  
    limit=10
)
```

---

#### 3. update
```python
async def update(self, item_id, item) -> bool
```

** :**
```python
updated_entity = UserEntity(
    nickname="",
    email="new@email.com"
)

success = await user_repo.update("user123", updated_entity)
```

---

#### 4. delete
```python
async def delete(self, **filters) -> bool
```

** :**
```python
#  
await repo.delete(id='user123')

#  
await repo.delete(user_id='user123', category_id='cat456')
```

---

##   Repository

### 1. CategoryRepository

()   

```python
async def get_review_statistics(
    id=None,                  #  ID 
    limit=None,               #  
    only_reviewed=False,      #   
    is_random=False,          #  
    order_by_rating=False     #  
) -> List[CategoryListItemDTO]
```

** :**
```python
#      10
categories = await repo.get_review_statistics(
    limit=10,
    only_reviewed=True,
    order_by_rating=True
)

#   
categories = await repo.get_review_statistics(
    id=['cat1', 'cat2', 'cat3']
)
```

**:**
- LEFT JOIN   
-  ,   
-   

---

### 2. TagsRepository

 

```python
async def select_last_id(category_type: int) -> int
    #     ID 
    #   ID  
```

---

### 3. StatisticsRepository

  

```python
async def get_total_users() -> dict
    #   

async def get_recommendation_stats() -> list
    #    

async def get_weekly_average_stats() -> list
    #   

async def get_popular_categories() -> list
    #  

async def get_popular_districts() -> list
    #  

async def get_template_stats() -> list
    #   

async def get_transportation_stats() -> list
    #  

async def get_daily_travel_time_stats() -> list
    #    

async def get_total_travel_time_avg() -> dict
    #    

async def get_transportation_travel_time_avg() -> list
    #   
```

---

##   

### 1.  CRUD
```python
class MyRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = my_table
        self.entity = MyEntity

    #    
    #  
```

### 2.  
```python
class CategoryRepository(BaseRepository):
    async def get_review_statistics(self, ...):
        #  JOIN 
        # base_repository select 
        return await self.select(
            joins=[...],
            columns={...}
        )
```

### 3. 
```python
# Repository    
async def some_method(self):
    engine = await get_engine()
    async with engine.begin() as conn:
        #   
        await conn.execute(stmt1)
        await conn.execute(stmt2)
        #  /
```

---

##   

### 1.  WHERE 
```python
# **filters    AND 
await repo.select(
    status='active',
    age=25,
    city='Seoul'
)
#  WHERE status='active' AND age=25 AND city='Seoul'
```

### 2. IN 
```python
#    IN  
await repo.select(
    id=['user1', 'user2', 'user3']
)
#  WHERE id IN ('user1', 'user2', 'user3')
```

### 3. JOIN with Alias
```python
#  alias   
columns={
    'user.nickname': 'author',
    'category.name': 'store_name'
}
```

### 4. 
```python
# 
order='created_at'

# 
order='-created_at'
```

---

##  

### 1. N+1  
```python
#   
for user in users:
    #     (N+1 )
    reviews = await review_repo.select(user_id=user.id)

#   
user_ids = [user.id for user in users]
# IN    
reviews = await review_repo.select(user_id=user_ids)
```

### 2. JOIN 
```python
#     
await repo.select(
    joins=[
        {'table': related_table, ...}
    ]
)
```

### 3.  
```python
#   
await repo.select(
    columns=['id', 'name'],  #    
    user_id='user123'
)
```

---

##   

###  Repository 
```python
from src.infra.database.repository.base_repository import BaseRepository
from src.infra.database.tables.table_my import my_table
from src.domain.entities.my_entity import MyEntity

class MyRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.table = my_table
        self.entity = MyEntity

    #  CRUD  
    
    #   
    async def get_active_items(self):
        return await self.select(status='active')
    
    async def search_by_name(self, keyword: str):
        #   
        pass
```

---
