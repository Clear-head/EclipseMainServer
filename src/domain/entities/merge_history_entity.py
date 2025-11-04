from datetime import datetime

from src.domain.entities.base_entity import BaseEntity


class MergeHistoryEntity(BaseEntity):
    id: str
    user_id: str
    template_type: str
    categories_name: str
    visited_at: datetime