from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class SessionData(BaseModel):
    user_id: str
    token_type: str
    created_at: datetime
    data: Optional[dict] = None

class ChatSessionData(BaseModel):
    play_address: str
    peopleCount: int
    selectedCategories: list
    collectedTags: dict
    currentCategoryIndex: int
    conversationHistory: list
    stage: str
    waitingForUserAction: bool
    lastUserMessage: str
    pendingTags: list
    modificationMode: bool
    randomCategories: list = []
    randomCategoryPending: Optional[str] = None