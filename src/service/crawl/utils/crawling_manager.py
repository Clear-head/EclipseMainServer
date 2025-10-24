"""
크롤링 작업 관리 모듈
크롤링과 저장 작업의 병렬 처리를 관리합니다.
"""
import asyncio
from typing import List, Tuple, Callable


class CrawlingManager:
    """크롤링 작업 매니저"""
    
    def __init__(self, source_name: str, logger):
        """
        Args:
            source_name: 크롤링 소스 이름 (예: 'Bluer', '강남구')
            logger: 로거 인스턴스
        """
        self.source_name = source_name
        self.logger = logger
        self.success_count = 0
        self.fail_count = 0
    
    async def execute_crawling_with_save(
        self,
        stores: List[Tuple],
        crawl_func: Callable,
        save_func: Callable,
        delay: int = 20
    ) -> Tuple[int, int]:
        """
        크롤링과 저장을 병렬로 실행
        
        Args:
            stores: 크롤링할 매장 목록
            crawl_func: 크롤링 함수 (store, idx, total) -> (store_data, actual_name) or None
            save_func: 저장 함수 (idx, total, store_data_tuple, store_name) -> (success, msg)
            delay: 크롤링 간 딜레이 (초)
            
        Returns:
            Tuple[int, int]: (성공 수, 실패 수)
        """
        total = len(stores)
        save_tasks = []
        
        self.logger.info(f"총 {total}개 {self.source_name} 매장 크롤링 시작")
        
        for idx, store in enumerate(stores, 1):
            initial_store_name = self._get_store_name(store)
            
            self.logger.info(f"[{self.source_name} 크롤링 {idx}/{total}] '{initial_store_name}' 크롤링 진행 중...")
            
            # 크롤링 실행
            crawl_result = await crawl_func(store, idx, total)
            
            if crawl_result:
                # 👇 실제 추출된 이름 사용
                store_data, actual_name = crawl_result
                
                self.logger.info(f"[{self.source_name} 크롤링 {idx}/{total}] '{actual_name}' 크롤링 완료")
                
                # 저장 태스크 생성 (백그라운드)
                save_task = asyncio.create_task(
                    save_func(idx, total, crawl_result, actual_name)
                )
                save_tasks.append(save_task)
                
                # 마지막이 아니면 딜레이
                if idx < total:
                    await asyncio.sleep(delay)
            else:
                self.fail_count += 1
                self.logger.error(f"[{self.source_name} 크롤링 {idx}/{total}] '{initial_store_name}' 크롤링 실패")
                
                # 실패해도 딜레이
                if idx < total:
                    await asyncio.sleep(delay)
        
        # 저장 작업 완료 대기
        self.logger.info(f"{self.source_name} 모든 크롤링 완료! 저장 작업 완료 대기 중... ({len(save_tasks)}개)")
        
        if save_tasks:
            save_results = await asyncio.gather(*save_tasks, return_exceptions=True)
            
            # 저장 결과 집계
            for result in save_results:
                if isinstance(result, Exception):
                    self.fail_count += 1
                elif isinstance(result, tuple):
                    success, msg = result
                    if success:
                        self.success_count += 1
                    else:
                        self.fail_count += 1
        
        self.logger.info(f"{self.source_name} 전체 작업 완료: 성공 {self.success_count}/{total}, 실패 {self.fail_count}/{total}")
        
        return self.success_count, self.fail_count
    
    @staticmethod
    def _get_store_name(store) -> str:
        """매장명 추출 (타입에 따라 다름)"""
        if isinstance(store, tuple):
            return str(store[-1]) if len(store) > 1 else str(store[0])
        elif isinstance(store, dict):
            return store.get('name', 'Unknown')
        elif isinstance(store, int):
            return f"장소 {store + 1}"
        else:
            return str(store)