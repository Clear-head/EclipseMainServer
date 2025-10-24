from src.domain.dto.header import JsonHeader
from src.domain.dto.service.main_screen_dto import MainScreenCategoryList, ResponseMainScreenBody, ResponseMainScreenDTO
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.tags_repository import TagsRepository


class MainService:

    def __init__(self):
        self.category_repo = CategoryRepository()
        self.reviews_repo = ReviewsRepository()
        self.category_tags_repo = CategoryTagsRepository()
        self.tags_repo = TagsRepository()


    async def to_main(self):
        categories = await self.category_repo.select_by(limit=5)

        tags = []

        request_main_screen_body_categories = []

        for item in categories:

            #   todo: 나중에 리펙토링 하기 여기 성능 문제 발생
            tag_in_category = await self.category_tags_repo.select_by(category_id=item.id)
            # reviews = await self.reviews_repo.select_by(category_id=item.id)

            for tag_item in tag_in_category:
                tag_entity = await self.tags_repo.select_by(tag_id=tag_item.id)
                if tag_entity is not None:
                    tags.extend(tag_entity[0].name)

            tmp = MainScreenCategoryList(
                id=item.id,
                image_url=item.image,
                detail_address=item.detail_address,
                sub_category=item.sub_category,
                phone=item.phone if item.phone is not None else None,
                title=item.name,
                tags=tags,
            )

            request_main_screen_body_categories.append(tmp)

        return ResponseMainScreenDTO(
            headers=JsonHeader(
                content_type="application/json",
                jwt=""
            ),
            body=ResponseMainScreenBody(
                categories=request_main_screen_body_categories,
            )
        )
