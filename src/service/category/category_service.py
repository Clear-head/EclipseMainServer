from fastapi import HTTPException

from src.domain.dto.category.category_detail_dto import ResponseCategoryDetailDTO, ReviewItemDTO
from src.domain.dto.category.category_dto import ResponseCategoryListDTO
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.tags_repository import TagsRepository
from src.infra.database.repository.user_like_repository import UserLikeRepository
from src.infra.database.repository.users_repository import UserRepository
from src.infra.database.tables.table_tags import tags_table
from src.infra.database.tables.table_users import users_table
from src.logger.custom_logger import get_logger
from src.utils.make_address import add_address


class MainScreenService:

    def __init__(self):
        self.category_repo = CategoryRepository()
        self.reviews_repo = ReviewsRepository()
        self.category_tags_repo = CategoryTagsRepository()
        self.tags_repo = TagsRepository()
        self.logger = get_logger(__name__)

    async def to_main(self, limit: int = 10) -> ResponseCategoryListDTO:
        categories = await self.category_repo.get_review_statistics(limit=limit, is_random=True)

        if not categories:
            return ResponseCategoryListDTO(categories=[])

        return ResponseCategoryListDTO(
            categories=categories,
        )

    async def get_category_detail(self, category_id: str, user_id: str) -> ResponseCategoryDetailDTO:
        category = await self.category_repo.select(id=category_id)

        if category is None or len(category) == 0:
            raise HTTPException(status_code=404, detail="Category not found")
        elif len(category) > 1:
            raise HTTPException(status_code=500, detail="Too many categories")

        category = category[0]

        like_result = await UserLikeRepository().select(
            category_id=category.id,
            user_id=user_id
        )
        is_like = bool(like_result)

        category_tags_with_names = await self.category_tags_repo.select(
            joins=[
                {
                    'table': tags_table,
                    'on': {'tag_id': 'id'},
                    'alias': 'tag',
                    'type': 'inner'
                }
            ],
            columns={
                'tag.name': 'tag_name',
                'count': 'count'
            },
            category_id=category.id,
            limit=5,
            order='count'
        )

        tag_names = [
            row['tag_name'].replace('"', '')
            for row in category_tags_with_names
            if row.get('tag_name')
        ]

        reviews_with_users = await self.reviews_repo.select(
            joins=[
                {
                    'table': users_table,
                    'on': {'user_id': 'id'},
                    'alias': 'user',
                    'type': 'inner'
                }
            ],
            columns={
                'id': 'review_id',
                'user_id': 'user_id',
                'category_id': 'category_id',
                'stars': 'stars',
                'comments': 'comments',
                'created_at': 'created_at',
                'user.nickname': 'nickname'
            },
            category_id=category.id
        )

        reviews_list = []
        total_stars = 0

        for review in reviews_with_users:
            total_stars += review['stars']
            reviews_list.append(
                ReviewItemDTO(
                    created_at=review['created_at'],
                    comment=review['comments'],
                    category_id=review['category_id'],
                    category_name=category.name,
                    stars=review['stars'],
                    review_id=review['review_id'],
                    nickname=review['nickname']
                )
            )

        average_stars = round(total_stars / len(reviews_list), 2) if reviews_list else 0

        detail_address = add_address(
            category.do,
            category.si,
            category.gu,
            category.detail_address
        )

        self.logger.info(
            f"카테고리 상세 조회 완료: {category_id}, "
            f"태그 {len(tag_names)}개, 리뷰 {len(reviews_list)}개"
        )

        return ResponseCategoryDetailDTO(
            id=category_id,
            title=category.name,
            image_url=category.image,
            sub_category=category.sub_category,
            detail_address=detail_address,
            is_like=is_like,
            tags=tag_names,
            menu_preview=self._extract_menu_preview(category.menu),
            reviews=reviews_list,
            average_stars=average_stars
        )

    async def rg_to_main(self) -> ResponseCategoryListDTO:
        categories = await self.category_repo.get_review_statistics(limit=10, is_random=True)

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

            # address = add_address(item.do, item.si, item.gu, item.detail_address)

        return ResponseCategoryListDTO(
            categories=categories,
        )


    async def rg_get_category_detail(self, category_id, user_id) -> ResponseCategoryDetailDTO:
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
        result = await repo.select(category_id=category.id, user_id=user_id)
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
        average_stars = 0

        reviews_list = []
        review_entity_list = await self.reviews_repo.select(category_id=category.id)
        if review_entity_list:
            for review_entity in review_entity_list:
                nickname = (await user_repo.select(id=review_entity.user_id))[0].nickname
                average_stars += review_entity.stars
                reviews_list.append(
                    ReviewItemDTO(
                        created_at=review_entity.created_at,
                        comment=review_entity.comments,
                        category_id=review_entity.category_id,
                        category_name=category.name,
                        stars=review_entity.stars,
                        review_id=review_entity.id,
                        nickname=nickname,
                    )
                )

        average_stars = round(average_stars/len(reviews_list), 2) if average_stars > 0 else 0

        return ResponseCategoryDetailDTO(
            id=category_id,
            title=category.name,
            image_url=category.image,
            sub_category=category.sub_category,
            detail_address= add_address(category.do, category.si, category.gu, category.detail_address),
            is_like=is_like,
            tags=tag_names,
            menu_preview=self._extract_menu_preview(category.menu), # 메뉴 컬럼 추가
            reviews=reviews_list,
            average_stars=average_stars
        )

    @staticmethod  # 메뉴 텍스트를 쉼표 기준으로 잘라 최대 limit개까지 목록으로 변환
    def _extract_menu_preview(menu_text: str | None, limit: int = 10) -> list[str]:
        if not menu_text:
            return []

        candidates = [item.strip() for item in menu_text.split(",")]
        menu_items = [item for item in candidates if item]

        return menu_items[:limit]