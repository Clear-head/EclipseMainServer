from collections import defaultdict

from src.domain.dto.history.history_dto import ResponseHistoryDetailDTO, HistoryDetailItemDTO, ResponseHistoryListDTO, \
    HistoryListItemDTO
from src.domain.dto.review.review_dto import ResponseReviewListDTO, ReviewDTO
from src.infra.database.repository.merge_history_repository import MergeHistoryRepository
from src.infra.database.repository.reviews_repository import ReviewsRepository
from src.infra.database.repository.user_history_repository import UserHistoryRepository
from src.infra.database.tables.table_category import category_table
from src.infra.database.tables.table_merge_history import merge_history_table
from src.logger.custom_logger import get_logger
from src.utils.make_address import add_address


class HistoryService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.repo = UserHistoryRepository()
        self.merge_repo = MergeHistoryRepository()

    #   히스토리 목록 조회
    async def get_user_history_list(self, user_id, is_post=False):
        self.logger.info(f"try {user_id} get user history list: {user_id}")

        if not is_post:
            result = await self.merge_repo.select(
                user_id=user_id,
                order="visited_at"
            )
        else:
            result = await self.merge_repo.select(
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

        template_type = (await MergeHistoryRepository().select(id=merge_history_id))[0].template_type

        result = await self.repo.select(
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

            # user_id와 category_id가 일치하는 히스토리 조회
            histories = await self.repo.select(
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
        (limit 개수만큼 찾으면 조기 종료)
        """
        try:
            self.logger.info(f"리뷰 작성 가능한 매장 조회 시작 - user_id: {user_id}, limit: {limit}")

            history_repo = self.repo
            histories = await history_repo.select(user_id=user_id)

            if not histories:
                self.logger.info(f"방문 기록이 없음 - user_id: {user_id}")
                return ResponseReviewListDTO(review_list=[])

            # 방문 정보 집계 (카테고리 정보도 함께 저장)
            visit_info = defaultdict(lambda: {
                "count": 0,
                "last_date": None,
                "category_name": "",
                "category": None  # 첫 번째 history의 category 정보 저장
            })

            for history in histories:
                category_id = history.category_id
                visit_info[category_id]["count"] += 1
                visit_info[category_id]["category_name"] = history.category_name

                # 첫 방문 시 category 객체 저장 (재조회 방지)
                if visit_info[category_id]["category"] is None:
                    visit_info[category_id]["category"] = history

                if visit_info[category_id]["last_date"] is None or \
                        history.visited_at > visit_info[category_id]["last_date"]:
                    visit_info[category_id]["last_date"] = history.visited_at

            self.logger.info(f"총 {len(visit_info)}개의 고유 매장 방문 기록")

            # 최신 방문순으로 정렬
            sorted_visits = sorted(
                visit_info.items(),
                key=lambda x: x[1]["last_date"],
                reverse=True
            )

            category_ids = [cat_id for cat_id, _ in sorted_visits]
            reviews_repo = ReviewsRepository()

            all_reviews = await reviews_repo.select(
                user_id=user_id,
                category_ids=category_ids
            )

            # category_id별로 리뷰 개수 집계
            review_counts = defaultdict(int)
            for review in all_reviews:
                review_counts[review.category_id] += 1

            reviewable_list = []
            checked_count = 0

            # limit 개수만큼 찾으면 중단
            for category_id, info in sorted_visits:
                if len(reviewable_list) >= limit:
                    self.logger.info(f"✅ {limit}개 찾음 - 조기 종료 (총 {checked_count}개 확인)")
                    break

                checked_count += 1
                visit_count = info["count"]
                review_count = review_counts.get(category_id, 0)

                # 리뷰 작성 가능 여부 확인
                if visit_count > review_count:
                    # 이미 저장된 history에서 category 정보 사용 (DB 재조회 불필요)
                    history_data = info["category"]

                    category_type_str = str(history_data.category_type) if hasattr(history_data,'category_type') and history_data.category_type is not None else ""

                    # history에 주소 정보가 있다면 활용
                    address = add_address(
                        history_data.do if hasattr(history_data, 'do') else "",
                        history_data.si if hasattr(history_data, 'si') else "",
                        history_data.gu if hasattr(history_data, 'gu') else "",
                        history_data.detail_address if hasattr(history_data, 'detail_address') else ""
                    )

                    reviewable_list.append(
                        ReviewDTO(
                            review_id="",
                            category_id=category_id,
                            category_name=info["category_name"],
                            category_type=category_type_str,
                            comment=address,
                            stars=visit_count,
                            created_at=info["last_date"],
                            nickname=None
                        )
                    )

                    self.logger.debug(
                        f"✅ [{len(reviewable_list)}/{limit}] {info['category_name']}: "
                        f"방문 {visit_count}회, 리뷰 {review_count}개"
                    )

            self.logger.info(f"최종 결과: {len(reviewable_list)}개 (총 {checked_count}개 매장 확인)")
            return ResponseReviewListDTO(review_list=reviewable_list)

        except Exception as e:
            self.logger.error(f"리뷰 작성 가능한 매장 조회 중 오류: {e}")
            return ResponseReviewListDTO(review_list=[])