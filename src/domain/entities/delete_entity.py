from src.domain.entities.base_entity import BaseEntity


class DeleteEntity(BaseEntity):
    cause: str
    count: int = 0