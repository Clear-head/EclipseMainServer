# External

 API  .

##  

```
external/
 kakao_map.py              #  API
 weather_api.py            #  API (data.go.kr)
 query_enchantment.py      # GPT-4 API ( )
```

##  Kakao Map API

 API       

###  

#### 1.   
```python
async def get_walking_route(origin: str, destination: str)
    # origin, destination: "," 
    # : (m), ()
```

** :**
```python
result = await kakao_api.get_walking_route(
    origin="127.123456,37.123456",
    destination="127.234567,37.234567"
)
# {
#   "distance": 1500,        # 
#   "duration": 1200         # 
# }
```

#### 2.   
```python
async def get_car_route(origin: str, destination: str)
    #    
```

### API 

** :**
```env
KAKAO_REST_API_KEY=your_kakao_rest_api_key
```

**:**
- : `https://apis-navi.kakaomobility.com/v1/directions`
- : `https://apis-navi.kakaomobility.com/v1/car/directions`

###  

```json
{
  "routes": [{
    "summary": {
      "distance": 1500,      // 
      "duration": 1200       // 
    }
  }]
}
```

---

##  Weather API

(data.go.kr)  API

###  

####   
```python
async def get_weather(nx: int, ny: int, base_date: str, base_time: str)
    # nx, ny:   
    # base_date: YYYYMMDD
    # base_time: HHmm
    # : , ,  
```

** :**
```python
weather = await weather_api.get_weather(
    nx=60,
    ny=127,
    base_date="20240101",
    base_time="0600"
)
```

### API 

** :**
```env
WEATHER_API_KEY=your_data_go_kr_api_key
```

**:**
```
http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst
```

###  

- **TMP**:  ()
- **POP**:  (%)
- **SKY**:  (1: , 3: , 4: )
- **PTY**:  (0: , 1: , 2: /, 3: )

---

##  Query Enhancement (GPT-4)

GPT-4      

###  

#### 1.   
```python
async def validate_user_input(user_message: str, category: str) -> tuple
    #    
    # : (result_type, error_message)
    # result_type: "valid", "invalid", "random"
```

** :**
```python
result_type, error = await query_enhancer.validate_user_input(
    user_message="  ",
    category=""
)

if result_type == "valid":
    #      
elif result_type == "random":
    #      
elif result_type == "invalid":
    #     
```

** :**
- **valid**:   
- **random**: "", "", "" 
- **invalid**: "", "111", "test"   

---

#### 2.  
```python
async def extract_tags_from_message(
    user_message: str,
    category: str,
    people_count: int
) -> List[str]
```

** :**
```python
tags = await query_enhancer.extract_tags_from_message(
    user_message="    2   ",
    category="",
    people_count=2
)
# [" ", "", " "]
```

**:**
-    
-    
-    

---

#### 3.  
```python
async def filter_recommendations_with_gpt(
    stores: List[Dict],
    user_keywords: List[str],
    category_type: str,
    personnel: int,
    max_results: int = 10,
    fill_with_original: bool = False
) -> List[Dict]
```

** :**
```python
filtered = await query_enhancer.filter_recommendations_with_gpt(
    stores=candidate_stores,      # 15 
    user_keywords=[" ", ""],
    category_type="",
    personnel=2,
    max_results=10                # 10 
)
```

** :**
1.   JSON 
2. GPT-4  
3.   
4.  N 

**GPT  :**
-  
-  
-  
- / 

---

### API 

** :**
```env
OPENAI_API_KEY=your_openai_api_key
```

** :**
- `gpt-4-turbo-preview` ()
- `gpt-4o` ()

###  

####   
```
 {category}    :
"{user_message}"

   :
1. valid:    
2. random:    
3. invalid:  

 :
{
  "type": "valid|random|invalid",
  "reason": " "
}
```

####   
```
 {category}  {people_count}  .
: "{user_message}"

  :
- /  
- /  
-  5

 :
["1", "2", "3"]
```

####  
```
     :
: {user_keywords}
: {personnel}
: {category_type}

 :
{stores_json}

  0-100  .

 :
{
  "rankings": [
    {"id": "ID", "score": , "reason": ""}
  ]
}
```

---

##   

### 1. API  
```python
import requests
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)

async def call_external_api(url: str, headers: dict, params: dict):
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"API  : {e}")
        raise
```

### 2.  
```python
try:
    result = await external_api.some_method()
except Exception as e:
    logger.error(f" API : {e}")
    #     
    return default_value
```

### 3.  
```python
response = requests.get(
    url,
    timeout=10  # 10 
)
```

---

##   

### Kakao Map API
- ** **:    ( )
- **  **: ~200ms
- ****:  ( 300,000 )

### Weather API
- ** **:  ( )
- **  **: ~500ms
- ****: 

### OpenAI GPT-4 API
- ** **:  ( AI )
- **  **: ~2-3
- ****: 
  - Input: $0.01 / 1K tokens
  - Output: $0.03 / 1K tokens

---

##  

### 1. API  
```python
#   
api_key = "your_api_key"

#    
import os
api_key = os.getenv("KAKAO_API_KEY")
```

### 2. Rate Limiting
```python
# API   
import asyncio

async def rate_limited_call():
    await asyncio.sleep(0.1)  #  
    return await api_call()
```

### 3.  
```python
#  API  
try:
    result = await external_api()
except:
    #  
    result = get_cached_or_default()
```

---
