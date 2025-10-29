from starlette.responses import JSONResponse

from src.domain.dto.service.main_screen_dto import MainScreenCategoryList, ResponseMainScreenDTO
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.tags_repository import TagsRepository


class MainScreenService:

    def __init__(self):
        self.category_repo = CategoryRepository()
        self.reviews_repo = ReviewsRepository()
        self.category_tags_repo = CategoryTagsRepository()
        self.tags_repo = TagsRepository()


    async def to_main(self):
        categories = await self.category_repo.select_by(limit=5)

        tags = []

        request_main_screen_body_categories = []
        limit = 5

        for item in categories:

            #   todo: 나중에 리펙토링 하기 여기 성능 문제 발생
            tag_in_category = await self.category_tags_repo.select_by(category_id=item.id, limit=limit)
            # reviews = await self.reviews_repo.select_by(category_id=item.id)

            for tag_item in tag_in_category:
                tag_entity = await self.tags_repo.select_by(tag_id=tag_item.id)
                if tag_entity is not None:
                    tags.extend(tag_entity[0].name)

            address = (
                    (item.do+" " if item.do is not None else "")+
                    (item.si+" " if item.si is not None else "")+
                    (item.gu+" " if item.gu is not None else "")+
                    (item.detail_address if item.detail_address is not None else "")
            )

            tmp = MainScreenCategoryList(
                id=item.id,
                image_url=item.image,
                detail_address=address,
                sub_category=item.sub_category,
                title=item.name
            )

            request_main_screen_body_categories.append(tmp)


        contents = ResponseMainScreenDTO(
            categories=request_main_screen_body_categories,
        )

        return JSONResponse(
            content=contents.model_dump(),
        )