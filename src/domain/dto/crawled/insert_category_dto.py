from pydantic import BaseModel


class InsertCategoryDto(BaseModel):
    name: str
    do: str
    si: str
    gu: str
    detail_address: str
    sub_category: str
    business_hour: str
    phone: str
    type: int
    image: str
    menu: str
    latitude: str
    longitude: str