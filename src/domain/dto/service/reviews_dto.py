from pydantic import BaseModel


class RequestSetReviewsDto(BaseModel):
    category_id: str
    stars: int
    comments: str
