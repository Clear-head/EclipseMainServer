"""
비동기 Chroma HTTP 클라이언트 래퍼 (chromadb.HttpClient를 asyncio.to_thread로 감싸서 사용)
"""
import asyncio
from typing import Optional, Dict, Any

import chromadb
from chromadb.config import Settings  # 필요 시 사용

DEFAULT_TENANT = "default"
DEFAULT_DATABASE = "main"

async def AsyncHttpClient(
    host: str = "localhost",
    port: int = 8081,
    ssl: bool = False,
    headers: Optional[Dict[str, str]] = None,
    settings: Optional[Settings] = None,
    tenant: str = DEFAULT_TENANT,
    database: str = DEFAULT_DATABASE,
):
    """
    chromadb.HttpClient를 생성하고 주요 메서드(컬렉션 조회/쿼리 등)를 asyncio.to_thread로 비동기 래핑한 클라이언트를 반환합니다.
    호출 예:
        client = await AsyncHttpClient(host="192.168.0.10", port=8081)
        stores = await client.get_collection("stores")
        results = await stores.query(query_embeddings=[...], n_results=10)
    """
    scheme = "https" if ssl else "http"
    base_url = f"{scheme}://{host}:{port}"

    # chromadb 버전마다 생성자 인자가 다를 수 있음: api_url / base_url 등 시도
    try:
        sync_client = chromadb.HttpClient(api_url=base_url, headers=headers)
    except TypeError:
        try:
            sync_client = chromadb.HttpClient(base_url=base_url, headers=headers)
        except TypeError:
            sync_client = chromadb.HttpClient(base_url, headers)

    class _AsyncCollection:
        def __init__(self, sync_collection):
            self._sync = sync_collection

        async def query(self, *args, **kwargs):
            return await asyncio.to_thread(self._sync.query, *args, **kwargs)

        async def add(self, *args, **kwargs):
            return await asyncio.to_thread(self._sync.add, *args, **kwargs)

        async def count(self):
            return await asyncio.to_thread(self._sync.count)

        # 필요에 따라 더 래핑

        @property
        def sync(self):
            return self._sync

    class _AsyncClient:
        def __init__(self, sync_client):
            self._sync = sync_client

        async def get_collection(self, name: str, *args, **kwargs):
            sync_col = await asyncio.to_thread(self._sync.get_collection, name, *args, **kwargs)
            return _AsyncCollection(sync_col)

        async def list_collections(self, *args, **kwargs):
            return await asyncio.to_thread(self._sync.list_collections, *args, **kwargs)

        async def create_collection(self, name: str, *args, **kwargs):
            sync_col = await asyncio.to_thread(self._sync.create_collection, name, *args, **kwargs)
            return _AsyncCollection(sync_col)

        async def reset(self, *args, **kwargs):
            return await asyncio.to_thread(self._sync.reset, *args, **kwargs)

        async def persist(self, *args, **kwargs):
            return await asyncio.to_thread(self._sync.persist, *args, **kwargs)

        # 동기 클라이언트가 제공하는 기타 메서드도 추가로 래핑 가능

        @property
        def sync(self):
            return self._sync

    return _AsyncClient(sync_client)