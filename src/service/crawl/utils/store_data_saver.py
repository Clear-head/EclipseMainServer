from typing import Tuple

from src.domain.dto.crawled.insert_category_dto import InsertCategoryDto
from src.domain.dto.crawled.insert_category_tags_dto import InsertCategoryTagsDTO
from src.infra.database.repository.category_repository import CategoryRepository
from src.infra.database.repository.category_tags_repository import CategoryTagsRepository
from src.infra.external.category_classifier_service import CategoryTypeClassifier
from src.infra.external.kakao_geocoding_service import GeocodingService
from src.logger.custom_logger import get_logger
from src.service.crawl.insert_crawled import insert_category, insert_category_tags, insert_tags
from src.service.crawl.update_crawled import update_category, update_category_tags
from src.service.crawl.utils.address_parser import AddressParser

logger = get_logger(__name__)

class StoreDataSaver:
    """상점 데이터 저장 클래스 (공통)"""
    
    def __init__(self):
        self.geocoding_service = GeocodingService()
        self.category_classifier = CategoryTypeClassifier()
    
    async def save_store_data(
        self, 
        idx: int, 
        total: int, 
        store_data: Tuple, 
        store_name: str,
        log_prefix: str = ""
    ) -> Tuple[bool, str]:
        """
        크롤링한 데이터를 DB에 저장하는 비동기 함수
        
        Args:
            idx: 현재 인덱스
            total: 전체 개수
            store_data: 크롤링한 상점 데이터 (name, full_address, phone, business_hours, image, sub_category, menu, tag_reviews, category_type)
            store_name: 상점명
            log_prefix: 로그 접두사 (예: "강남구")
            
        Returns:
            Tuple[bool, str]: (성공 여부, 로그 메시지)
        """
        try:
            name, full_address, phone, business_hours, image, sub_category, menu, tag_reviews, category_type = store_data
            
            # 주소 파싱
            do, si, gu, detail_address = AddressParser.parse_address(full_address)
            
            # 좌표만 변환 (카테고리 분류는 이미 완료됨)
            longitude, latitude = await self.geocoding_service.get_coordinates(full_address)
            
            # DTO 생성
            category_dto = InsertCategoryDto(
                name=name,
                do=do,
                si=si,
                gu=gu,
                detail_address=detail_address,
                sub_category=sub_category,
                business_hour=business_hours or "",
                phone=phone.replace('-', '') if phone else "",
                type=category_type,
                image=image or "",
                menu=menu or "",
                latitude=latitude or "",
                longitude=longitude or ""
            )
            
            # category 저장 (중복 체크 포함)
            category_repository = CategoryRepository()
            # select_by() → select()로 변경
            existing_categories = await category_repository.select(
                name=name,
                type=category_type,
                detail_address=detail_address
            )
            
            category_id = None
            
            # 중복 데이터가 있으면 update, 없으면 insert
            if len(existing_categories) == 1:
                category_id = await update_category(category_dto)
            elif len(existing_categories) == 0:
                category_id = await insert_category(category_dto)
            else:
                logger.error(f"[{log_prefix} 저장 {idx}/{total}] 중복 카테고리가 {len(existing_categories)}개 발견됨: {name}")
                raise Exception(f"중복 카테고리 데이터 무결성 오류: {name}")
            
            if category_id:
                # 태그 리뷰 저장 (중복 체크 포함)
                tag_success_count = 0
                for tag_name, tag_count in tag_reviews:
                    tag_name = tag_name.replace('"','')
                    try:
                        tag_id = await insert_tags(tag_name, category_type)
                        
                        if tag_id:
                            category_tags_dto = InsertCategoryTagsDTO(
                                tag_id=tag_id,
                                category_id=category_id,
                                count=tag_count
                            )
                            
                            category_tags_repository = CategoryTagsRepository()
                            # select_by() → select()로 변경
                            existing_tags = await category_tags_repository.select(
                                tag_id=tag_id,
                                category_id=category_id
                            )
                            
                            if len(existing_tags) == 1:
                                if await update_category_tags(category_tags_dto):
                                    tag_success_count += 1
                            elif len(existing_tags) == 0:
                                if await insert_category_tags(category_tags_dto):
                                    tag_success_count += 1
                            else:
                                logger.error(f"중복 태그가 {len(existing_tags)}개 발견됨")
                                
                    except Exception as tag_error:
                        logger.error(f"태그 저장 중 오류: {tag_name} - {tag_error}")
                        continue
                
                success_msg = f"[{log_prefix} 저장 {idx}/{total}] '{name}' 완료"
                logger.info(success_msg)
                return True, success_msg
            else:
                error_msg = f"[{log_prefix} 저장 {idx}/{total}] '{name}' DB 저장 실패"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as db_error:
            error_msg = f"[{log_prefix} 저장 {idx}/{total}] '{store_name}' DB 저장 중 오류: {db_error}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            return False, error_msg