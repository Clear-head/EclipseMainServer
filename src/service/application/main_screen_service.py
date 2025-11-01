from fastapi import HTTPException

from src.domain.dto.service.detail_category_dto import ResponseDetailCategoryDTO, DetailCategoryReview
from src.domain.dto.service.main_screen_dto import MainScreenCategoryList, ResponseMainScreenDTO
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.tags_repository import TagsRepository
from src.infra.database.repository.user_like_repository import UserLikeRepository
from src.infra.database.repository.users_repository import UserRepository


class MainScreenService:

    def __init__(self):
        self.category_repo = CategoryRepository()
        self.reviews_repo = ReviewsRepository()
        self.category_tags_repo = CategoryTagsRepository()
        self.tags_repo = TagsRepository()


    async def to_main(self) -> ResponseMainScreenDTO:
        categories = await self.category_repo.select(limit=5)

        tags = []

        request_main_screen_body_categories = []
        limit = 5

        for item in categories:

            #   todo: 나중에 리펙토링 하기 여기 성능 문제 발생
            tag_in_category = await self.category_tags_repo.select(category_id=item.id, limit=limit)
            # reviews = await self.reviews_repo.select_by(category_id=item.id)

            for tag_item in tag_in_category:
                tag_entity = await self.tags_repo.select(tag_id=tag_item.id)
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

        return ResponseMainScreenDTO(
            categories=request_main_screen_body_categories,
        )


    async def get_category_detail(self, category_id) -> ResponseDetailCategoryDTO:
        user_repo = UserRepository()


        category = await self.category_repo.select(id=category_id)

        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")
        elif len(category) > 1:
            raise HTTPException(status_code=404, detail="Too many categories")
        category = category[0]


        #   todo: 여기도 성능 잡아야 함 join 처리 해야 할 듯


        category_in_tags = await self.category_tags_repo.select(category_id=category.id, limit=5)

        #   is_like
        repo = UserLikeRepository()
        result = await repo.select(category_id=category.id)
        if result:
            is_like = True
        else:
            is_like = False


        #   tags
        tag_names = []
        for tag_ids in category_in_tags:
            tag_name = await self.tags_repo.select(id=tag_ids.tag_id)
            for i in tag_name:
                tag_names.append(i.name.replace("\"", ""))


        #   reviews
        reviews_list = []
        review_entity_list = await self.reviews_repo.select(category_id=category.id)
        for review_entity in review_entity_list:
            nickname = (await user_repo.select(id=review_entity.user_id))[0].nickname
            star = review_entity.star
            comment = review_entity.comment
            reviews_list.append(
                DetailCategoryReview(
                    nickname=nickname,
                    star=star,
                    comment=comment,
                )
            )

        return ResponseDetailCategoryDTO(
            is_like=is_like,
            tags=tag_names,
            reviews=reviews_list,
        )