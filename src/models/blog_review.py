from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class BlogReview(BaseModel):
    content: str
    create_at: Optional[datetime] = None
    
    def __init__(self, **data):
        super().__init__(**data)