from fastapi import HTTPException
from sqlalchemy import func

from src.domain.dto.category.category_detail_dto import ResponseCategoryDetailDTO, ReviewItemDTO
from src.domain.dto.category.category_dto import ResponseCategoryListDTO, CategoryListItemDTO
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.tags_repository import TagsRepository
from src.infra.database.repository.user_like_repository import UserLikeRepository
from src.infra.database.repository.users_repository import UserRepository
from src.utils.make_address import add_address


class MainScreenService:

    def __init__(self):
        self.category_repo = CategoryRepository()
        self.reviews_repo = ReviewsRepository()
        self.category_tags_repo = CategoryTagsRepository()
        self.tags_repo = TagsRepository()


    async def to_main(self) -> ResponseCategoryListDTO:
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

        print(categories)
        return ResponseCategoryListDTO(
            categories=categories,
        )


    async def get_category_detail(self, category_id, user_id) -> ResponseCategoryDetailDTO:
        user_repo = UserRepository()

        category = await self.category_repo.select(id=category_id)

        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")
        elif len(category) > 1:
            raise HTTPException(status_code=404, detail="Too many categories")
        category = category[0]

        # is_like
        repo = UserLikeRepository()
        result = await repo.select(category_id=category.id, user_id=user_id)
        is_like = bool(result)

        # 🔥 태그 정보 JOIN으로 한 번에 조회
        category_in_tags = await self.category_tags_repo.select(
            category_id=category.id, 
            limit=5
        )
        
        tag_names = []
        if category_in_tags:
            # 모든 tag_id를 리스트로 수집
            tag_ids = [tag.tag_id for tag in category_in_tags]
            
            # 한 번에 조회 (IN 절 사용)
            tags = await self.tags_repo.select(id=tag_ids)
            tag_names = [tag.name.replace("\"", "") for tag in tags]

        # 🔥 리뷰 정보 - 사용자 정보를 한 번에 조회
        average_stars = 0
        reviews_list = []
        
        review_entity_list = await self.reviews_repo.select(category_id=category.id)
        
        if review_entity_list:
            # 모든 user_id를 리스트로 수집
            user_ids = list(set([review.user_id for review in review_entity_list]))
            
            # 한 번에 조회 (IN 절 사용)
            users = await user_repo.select(id=user_ids)
            
            # user_id -> nickname 매핑
            user_map = {user.id: user.nickname for user in users}
            
            # 리뷰 목록 생성
            for review_entity in review_entity_list:
                nickname = user_map.get(review_entity.user_id, "알 수 없음")
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

        average_stars = round(average_stars/len(reviews_list), 2) if reviews_list else 0

        return ResponseCategoryDetailDTO(
            id=category_id,
            title=category.name,
            image_url=category.image,
            sub_category=category.sub_category,
            detail_address=add_address(category.do, category.si, category.gu, category.detail_address),
            is_like=is_like,
            tags=tag_names,
            menu_preview=self._extract_menu_preview(category.menu),
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
    
    
    async def get_categories_batch(
        self, 
        category_ids: list[str], 
        user_id: str
    ) -> list[ResponseCategoryDetailDTO]:
        """
        여러 카테고리를 한 번에 조회 (IN 절 활용)
        """
        try:
            # 1. 카테고리 기본 정보 조회 (IN 절로 한 번에)
            categories = await self.category_repo.select(id=category_ids)
            
            if not categories:
                return []
            
            # 2. 좋아요 정보도 한 번에 조회
            like_repo = UserLikeRepository()
            likes = await like_repo.select(
                user_id=user_id,
                category_id=category_ids
            )
            liked_set = {like.category_id for like in likes} if likes else set()
            
            # 3. 각 카테고리의 태그, 리뷰 정보 조회
            results = []
            
            for category in categories:
                # 태그 조회
                category_in_tags = await self.category_tags_repo.select(
                    category_id=category.id,
                    limit=5
                )
                
                tag_names = []
                if category_in_tags:
                    tag_ids = [tag.tag_id for tag in category_in_tags]
                    tags = await self.tags_repo.select(id=tag_ids)
                    tag_names = [tag.name.replace("\"", "") for tag in tags]
                
                # 리뷰 조회
                review_entity_list = await self.reviews_repo.select(
                    category_id=category.id
                )
                
                reviews_list = []
                average_stars = 0
                
                if review_entity_list:
                    user_ids = list(set([r.user_id for r in review_entity_list]))
                    users = await UserRepository().select(id=user_ids)
                    user_map = {user.id: user.nickname for user in users}
                    
                    for review_entity in review_entity_list:
                        nickname = user_map.get(review_entity.user_id, "알 수 없음")
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
                    
                    average_stars = round(average_stars / len(reviews_list), 2)
                
                results.append(
                    ResponseCategoryDetailDTO(
                        id=category.id,
                        title=category.name,
                        image_url=category.image,
                        sub_category=category.sub_category,
                        detail_address=add_address(
                            category.do,
                            category.si,
                            category.gu,
                            category.detail_address
                        ),
                        is_like=category.id in liked_set,
                        tags=tag_names,
                        menu_preview=self._extract_menu_preview(category.menu),
                        reviews=reviews_list,
                        average_stars=average_stars
                    )
                )
            
            return results
            
        except Exception as e:
            self.logger.error(f"일괄 카테고리 조회 오류: {e}")
            return []