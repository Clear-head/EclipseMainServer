from src.domain.dto.history.history_dto import ResponseHistoryListDTO, HistoryDetailItemDTO, HistoryListItemDTO, \
    ResponseHistoryDetailDTO
from src.domain.dto.like.like_dto import ResponseLikeListDTO, RequestToggleLikeDTO
from src.domain.dto.review.review_dto import ResponseReviewListDTO, ReviewDTO
from src.domain.dto.user.user_profile_dto import RequestUpdateProfileDTO, ResponseUpdateProfileDTO
from src.domain.entities.user_entity import UserEntity
from src.domain.entities.user_like_entity import UserLikeEntity
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.merge_history_repository import MergeHistoryRepository
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.user_history_repository import UserHistoryRepository
from src.infra.database.repository.user_like_repository import UserLikeRepository
from src.infra.database.repository.users_repository import UserRepository
from src.infra.database.tables.table_category import category_table
from src.infra.database.tables.table_merge_history import merge_history_table
from src.logger.custom_logger import get_logger
from src.utils.exception_handler.auth_error_class import UserNotFoundException, DuplicateUserInfoError
from src.utils.make_address import add_address
from collections import defaultdict


class UserInfoService:
    def __init__(self):
        self.logger = get_logger(__name__)

    #   내정보 수정
    async def change_info(self, dto: RequestUpdateProfileDTO, field: str, user_id):
        self.logger.info(f"try {field} change id: {user_id}")
        repo = UserRepository()

        result = await repo.select(id=user_id, password=dto.password)

        if not result:
            raise UserNotFoundException()

        elif len(result) > 1:
            raise DuplicateUserInfoError()

        else:
            result = result[0]

            if field == "nickname":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=dto.change_field,
                    password=result.password,
                    email=result.email,
                )

            elif field == "password":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=result.nickname,
                    password=dto.change_field,
                    email=result.email,
                )

            elif field == "email":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=result.nickname,
                    email=dto.change_field,
                    password=result.password
                )

            elif field == "address":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=result.nickname,
                    email=result.email,
                    address=dto.change_field,
                    password=result.password,
                )

            elif field == "phone":
                user_entity = UserEntity(
                    id=user_id,
                    username=result.username,
                    nickname=result.nickname,
                    email=result.email,
                    password=result.password,
                    phone=dto.change_field,
                )

            await repo.update(user_id, user_entity)

        return ResponseUpdateProfileDTO(
            msg=dto.change_field
        )


    #   좋아요 설정
    async def set_my_like(self, data: RequestToggleLikeDTO, type: bool, user_id: str) -> str:
        self.logger.info(f"try {user_id} set my like: {type}")
        repo = UserLikeRepository()

        if not type:
            flag = await repo.delete(user_id=user_id, category_id=data.category_id)
        else:
            flag = await repo.insert(
                UserLikeEntity(
                    user_id=user_id,
                    category_id=data.category_id
                )
            )

        if not flag:
            self.logger.error(f"찜 목록 설정 실패 user: {user_id}, category: {data.category_id}")
            raise Exception(f"찜 목록 설정 실패 user: {user_id}, category: {data.category_id}")

        else:
            return "success"


    #   좋아요 목록 조회
    async def get_user_like(self, user_id) -> ResponseLikeListDTO:
        self.logger.info(f"try {user_id} get user like: {user_id}")
        repo = UserLikeRepository()

        liked = await repo.select(user_id=user_id)

        if not liked:
            self.logger.info(f"no like for {user_id}")
            return ResponseLikeListDTO(
                like_list=[]
            )

        else:
            ans = await CategoryRepository().get_review_statistics(
                id=[i.category_id for i in liked],
                is_random=False
            )
            return ResponseLikeListDTO(
                like_list=ans
            )


    #   히스토리 목록 조회
    async def get_user_history_list(self, user_id, is_post=False):
        self.logger.info(f"try {user_id} get user history list: {user_id}")
        repo = MergeHistoryRepository()

        if not is_post:
            result = await repo.select(
                user_id=user_id,
                order="visited_at"
            )
        else:
            result = await repo.select(
                user_id=user_id,
                order="visited_at",
                limit=10
            )
        
        results = [
            HistoryListItemDTO(
                id=item.id,
                visited_at=item.visited_at,
                categories_name=item.categories_name,
                template_type=item.template_type
            )
            for item in result
        ]

        return ResponseHistoryListDTO(
            results=results
        )


    #   히스토리 디테일 조회
    async def get_user_history_detail(self, user_id, merge_history_id):
        self.logger.info(f"try {user_id} get user history: {user_id}")
        repo = UserHistoryRepository()


        template_type = (await MergeHistoryRepository().select(id=merge_history_id))[0].template_type

        result = await repo.select(
            user_id=user_id,
            merge_id=merge_history_id,
            joins=[
                {
                    "table": merge_history_table,
                    "on": {"merge_id": "id"},
                    "alias": "merge_history"
                },
                {
                    "table": category_table,
                    "on": {"category_id": "id"},
                    "alias": "category"
                }
            ],
            columns={
                "category.id": "id",
                "category.name": "category_name",
                "category.type": "type",
                "category.sub_category": "sub_category",
                "category.do": "do",
                "category.si": "si",
                "category.gu": "gu",
                "category.detail_address": "detail_address",
                "category.image": "image",
                "transportation": "transportation",
                "seq": "seq",
                "duration": "duration",
                "description": "description",
                "merge_history.visited_at": "visited_at"
            }
        )

        tmp = []

        for i in result:

            address = add_address(i.do, i.si, i.gu, i.detail_address)

            tmp.append(
                HistoryDetailItemDTO(
                    category_id=i.id,
                    category_name=i.category_name,
                    duration=i.duration,
                    transportation=i.transportation,
                    seq=i.seq,
                    image=i.image,
                    category_type=i.type,
                    sub_category=i.sub_category,
                    category_detail_address=address,
                    description=i.description,
                    visited_at=i.visited_at
                )
            )

        tmp = sorted(tmp, key=lambda x: x.seq)

        return ResponseHistoryDetailDTO(
            template_type=template_type,
            categories=tmp
        )


    # 🔥 추가: 특정 카테고리 방문 횟수 조회
    async def get_category_visit_count(self, user_id: str, category_id: str) -> int:
        """
        특정 사용자가 특정 카테고리(매장)를 방문한 횟수를 조회합니다.
        user_history 테이블에서 해당 user_id와 category_id가 일치하는 레코드 개수를 반환합니다.
        
        Args:
            user_id: 사용자 ID
            category_id: 카테고리(매장) ID
            
        Returns:
            int: 방문 횟수
        """
        try:
            self.logger.info(f"try get visit count for user: {user_id}, category: {category_id}")
            
            repo = UserHistoryRepository()
            
            # user_id와 category_id가 일치하는 히스토리 조회
            histories = await repo.select(
                user_id=user_id,
                category_id=category_id
            )
            
            count = len(histories) if histories else 0
            
            self.logger.info(f"user {user_id} visited category {category_id} {count} times")
            
            return count
            
        except Exception as e:
            self.logger.error(f"Error getting visit count: {e}")
            # 오류 발생 시 0 반환 (안전한 기본값)
            return 0
        
    async def get_reviewable_stores(self, user_id: str, limit: int = 6) -> ResponseReviewListDTO:
        """
        리뷰 작성 가능한 매장 목록을 조회합니다.
        (방문 횟수 > 리뷰 개수인 매장만 반환, 최신 방문순)
        
        Args:
            user_id: 사용자 ID
            limit: 최대 반환 개수 (기본값: 6)
            
        Returns:
            ResponseReviewListDTO: 리뷰 작성 가능한 매장 정보 (ReviewDTO 형식)
        """
        try:
            self.logger.info(f"리뷰 작성 가능한 매장 조회 시작 - user_id: {user_id}")
            
            # 1. 사용자의 방문 기록 조회
            history_repo = UserHistoryRepository()
            histories = await history_repo.select(user_id=user_id)
            
            if not histories:
                self.logger.info(f"방문 기록이 없음 - user_id: {user_id}")
                return ResponseReviewListDTO(review_list=[])
            
            # 2. category_id별 방문 정보 집계 (방문 횟수, 마지막 방문일)
            visit_info = defaultdict(lambda: {"count": 0, "last_date": None, "category_name": ""})
            
            for history in histories:
                category_id = history.category_id
                visit_info[category_id]["count"] += 1
                visit_info[category_id]["category_name"] = history.category_name
                
                # 마지막 방문일 업데이트
                if visit_info[category_id]["last_date"] is None or \
                history.visited_at > visit_info[category_id]["last_date"]:
                    visit_info[category_id]["last_date"] = history.visited_at
            
            self.logger.info(f"총 {len(visit_info)}개의 고유 매장 방문 기록")
            
            # 3. 각 카테고리별 리뷰 개수 조회 및 필터링
            reviews_repo = ReviewsRepository()
            category_repo = CategoryRepository()
            reviewable_list = []
            
            for category_id, info in visit_info.items():
                visit_count = info["count"]
                last_visit_date = info["last_date"]
                category_name = info["category_name"]
                
                # 해당 카테고리에 작성한 리뷰 개수 조회
                reviews = await reviews_repo.select(
                    user_id=user_id,
                    category_id=category_id
                )
                review_count = len(reviews) if reviews else 0
                
                # 리뷰 작성 가능 여부 확인 (방문 횟수 > 리뷰 개수)
                if visit_count > review_count:
                    # 카테고리 정보 조회
                    category = await category_repo.select(id=category_id)
                    
                    if category and len(category) > 0:
                        cat = category[0]
                        
                        # 🔥 category_type을 문자열로 변환
                        category_type_str = str(cat.type) if cat.type is not None else ""
                        
                        # 🔥 주소 정보 생성
                        address = add_address(cat.do, cat.si, cat.gu, cat.detail_address)
                        
                        # ReviewDTO 형식으로 변환 (재사용)
                        reviewable_list.append(
                            ReviewDTO(
                                review_id="",  # 리뷰 ID는 빈 값
                                category_id=cat.id,
                                category_name=cat.name,
                                category_type=category_type_str,
                                comment=address,  # 🔥 주소 정보로 변경
                                stars=visit_count,  # 🔥 방문 횟수는 stars에 저장
                                created_at=last_visit_date,  # 마지막 방문일
                                nickname=None
                            )
                        )
                        
                        self.logger.info(
                            f"✅ {cat.name}: 방문 {visit_count}회, 리뷰 {review_count}개 - 작성 가능"
                        )
                    else:
                        self.logger.warning(f"카테고리 정보를 찾을 수 없음 - category_id: {category_id}")
                else:
                    self.logger.info(
                        f"⏭️ {category_name}: 방문 {visit_count}회, 리뷰 {review_count}개 - 작성 완료"
                    )
            
            # 4. 최신 방문순으로 정렬 및 제한
            reviewable_list.sort(key=lambda x: x.created_at, reverse=True)
            limited_list = reviewable_list[:limit]
            
            self.logger.info(f"최종 리뷰 작성 가능한 매장: {len(limited_list)}개")
            
            return ResponseReviewListDTO(review_list=limited_list)
            
        except Exception as e:
            self.logger.error(f"리뷰 작성 가능한 매장 조회 중 오류: {e}")
            return ResponseReviewListDTO(review_list=[])