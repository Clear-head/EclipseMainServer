import json
from typing import Optional

import redis.asyncio as redis

from src.logger.custom_logger import get_logger
from src.utils.path import path_dic

logger = get_logger(__name__)


class RedisConnector:
    _instance: Optional['RedisConnector'] = None
    _client: Optional[redis.Redis] = None
    _config: Optional[dict] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()

    def _load_config(self):
        try:
            config_path = path_dic["redis_config"]
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        except Exception as e:
            logger.error(e)
            raise e

    async def connect(self) -> redis.Redis:
        if self._client is not None:
            return self._client

        try:
            self._client = redis.Redis(
                host=self._config.get("host", "localhost"),
                port=self._config.get("port", 6379),
                password=self._config.get("password"),
                db=self._config.get("db", 0),
                decode_responses=self._config.get("decode_responses", True),
                max_connections=self._config.get("max_connections", 50),
                socket_timeout=self._config.get("socket_timeout", 5),
                socket_connect_timeout=self._config.get("socket_connect_timeout", 5)
            )

            await self._client.ping()
            return self._client

        except Exception as e:
            logger.error(f"Redis 연결 실패: {e}")
            raise

    async def get_client(self) -> redis.Redis:
        if self._client is None:
            await self.connect()
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.close()
            self._client = None

    def get_session_config(self) -> dict:
        return self._config.get("session", {})


async def get_redis() -> redis.Redis:
    client = RedisConnector()
    return await client.get_client()


async def close_redis():
    client = RedisConnector()
    await client.close()