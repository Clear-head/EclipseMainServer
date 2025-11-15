"""
비동기 Chroma HTTP 클라이언트 래퍼
"""
import asyncio
from typing import Optional, Dict

import chromadb

DEFAULT_TENANT = "default"
DEFAULT_DATABASE = "main"


async def AsyncHttpClient(
    host: str = "localhost",
    port: int = 8081,
    ssl: bool = False,
    headers: Optional[Dict[str, str]] = None,
    tenant: str = DEFAULT_TENANT,
    database: str = DEFAULT_DATABASE,
):
    """
    chromadb.HttpClient를 생성하고 주요 메서드를 asyncio.to_thread로 비동기 래핑합니다.
    
    Args:
        host: Chroma 서버 호스트
        port: Chroma 서버 포트 (예: 8081)
        ssl: HTTPS 사용 여부
        headers: 추가 HTTP 헤더
        tenant: 테넌트 이름
        database: 데이터베이스 이름
        
    Returns:
        _AsyncClient: 비동기 클라이언트 래퍼
    """
    scheme = "https" if ssl else "http"

    # chromadb 버전에 따라 생성자 인자가 다를 수 있음
    try:
        # 최신 버전 시도
        sync_client = chromadb.HttpClient(
            host=host, 
            port=port, 
            ssl=ssl, 
            headers=headers
        )
    except TypeError:
        try:
            # 구버전 시도
            sync_client = chromadb.HttpClient(
                host=host, 
                port=port, 
                headers=headers
            )
        except TypeError:
            # 가장 기본적인 방식
            sync_client = chromadb.HttpClient(
                host=f"{host}:{port}"
            )

    class _AsyncCollection:
        """비동기 컬렉션 래퍼"""
        
        def __init__(self, sync_collection):
            self._sync = sync_collection

        async def query(self, *args, **kwargs):
            """벡터 유사도 검색"""
            return await asyncio.to_thread(self._sync.query, *args, **kwargs)

        async def add(self, *args, **kwargs):
            """문서 추가"""
            return await asyncio.to_thread(self._sync.add, *args, **kwargs)

        async def get(self, *args, **kwargs):
            """문서 조회"""
            return await asyncio.to_thread(self._sync.get, *args, **kwargs)

        async def count(self):
            """문서 개수"""
            return await asyncio.to_thread(self._sync.count)

        async def peek(self, *args, **kwargs):
            """샘플 조회"""
            return await asyncio.to_thread(self._sync.peek, *args, **kwargs)

        async def update(self, *args, **kwargs):
            """문서 업데이트"""
            return await asyncio.to_thread(self._sync.update, *args, **kwargs)

        async def delete(self, *args, **kwargs):
            """문서 삭제"""
            return await asyncio.to_thread(self._sync.delete, *args, **kwargs)

        @property
        def name(self):
            return self._sync.name

        @property
        def sync(self):
            """동기 컬렉션 객체 직접 접근 (주의해서 사용)"""
            return self._sync

    class _AsyncClient:
        """비동기 클라이언트 래퍼"""
        
        def __init__(self, sync_client):
            self._sync = sync_client

        async def get_collection(self, name: str, *args, **kwargs):
            """컬렉션 조회"""
            sync_col = await asyncio.to_thread(
                self._sync.get_collection, name, *args, **kwargs
            )
            return _AsyncCollection(sync_col)

        async def list_collections(self, *args, **kwargs):
            """전체 컬렉션 목록"""
            return await asyncio.to_thread(
                self._sync.list_collections, *args, **kwargs
            )

        async def create_collection(self, name: str, *args, **kwargs):
            """컬렉션 생성"""
            sync_col = await asyncio.to_thread(
                self._sync.create_collection, name, *args, **kwargs
            )
            return _AsyncCollection(sync_col)

        async def get_or_create_collection(self, name: str, *args, **kwargs):
            """컬렉션 조회 또는 생성"""
            sync_col = await asyncio.to_thread(
                self._sync.get_or_create_collection, name, *args, **kwargs
            )
            return _AsyncCollection(sync_col)

        async def delete_collection(self, name: str, *args, **kwargs):
            """컬렉션 삭제"""
            return await asyncio.to_thread(
                self._sync.delete_collection, name, *args, **kwargs
            )

        async def reset(self, *args, **kwargs):
            """전체 리셋"""
            return await asyncio.to_thread(
                self._sync.reset, *args, **kwargs
            )

        async def heartbeat(self):
            """서버 연결 상태 확인"""
            return await asyncio.to_thread(self._sync.heartbeat)

        @property
        def sync(self):
            """동기 클라이언트 객체 직접 접근 (주의해서 사용)"""
            return self._sync

    return _AsyncClient(sync_client)