from datetime import datetime, timezone
from typing import Optional, List, Dict

from src.domain.dto.session.session_dto import SessionData, ChatSessionData
from src.infra.cache.redis_connector import RedisConnector
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


class SessionRepository:
    def __init__(self):
        self.client = RedisConnector()
        self.config = self.client.get_session_config()
        self.prefix = self.config.get("prefix", "session:")
        self.chat_prefix = f"{self.prefix}chat:"

    async def set_session(
            self,
            session_id: str,
            user_id: str,
            token_type: str,
            ttl: int,
            data: Optional[dict] = None
    ) -> bool:
        """
        JWT 세션 저장 (Access/Refresh Token)

        Args:
            session_id: JWT token (key로 사용)
            user_id: 사용자 ID
            token_type: "access" | "refresh"
            ttl: 만료 시간 (초) - JWT exp에서 계산된 값
            data: 추가 데이터
        """
        try:
            redis_client = await self.client.get_client()

            # Pydantic 모델 사용
            session_data = SessionData(
                user_id=user_id,
                token_type=token_type,
                created_at=datetime.now(timezone.utc),
                data=data
            )

            key = f"{self.prefix}{session_id}"
            value = session_data.model_dump_json()

            await redis_client.setex(key, ttl, value)

            logger.debug(f"세션 저장 성공: user_id={user_id}, type={token_type}, ttl={ttl}s")
            return True

        except Exception as e:
            logger.error(f"세션 저장 실패: {e}")
            return False

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        JWT 세션 조회

        Args:
            session_id: JWT token

        Returns:
            SessionData 또는 None
        """
        try:
            redis_client = await self.client.get_client()

            key = f"{self.prefix}{session_id}"
            value = await redis_client.get(key)

            if not value:
                logger.debug(f"세션 없음: {session_id[:20]}...")
                return None

            session_data = SessionData.model_validate_json(value)
            logger.debug(f"세션 조회 성공: user_id={session_data.user_id}")

            return session_data

        except Exception as e:
            logger.error(f"세션 조회 실패: {e}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """
        JWT 세션 삭제 (로그아웃)

        Args:
            session_id: JWT token
        """
        try:
            redis_client = await self.client.get_client()

            key = f"{self.prefix}{session_id}"
            result = await redis_client.delete(key)

            if result > 0:
                logger.info(f"세션 삭제 성공: {session_id[:20]}...")
                return True
            else:
                logger.warning(f"삭제할 세션 없음: {session_id[:20]}...")
                return False

        except Exception as e:
            logger.error(f"세션 삭제 실패: {e}")
            return False

    # ==================== AI 채팅 세션 전용 메서드 ====================

    async def set_chat_session(
            self,
            user_id: str,
            chat_data: Dict,
            ttl: int = 1800
    ) -> bool:
        """
        AI 채팅 세션 저장

        Args:
            user_id: 사용자 ID (key로 사용)
            chat_data: 채팅 세션 데이터 (dict 또는 ChatSessionData)
            ttl: 만료 시간 (초, 기본 30분)
        """
        try:
            redis_client = await self.client.get_client()

            # dict인 경우 Pydantic 모델로 변환
            if isinstance(chat_data, dict):
                session_model = ChatSessionData(**chat_data)
            else:
                session_model = chat_data

            key = f"{self.chat_prefix}{user_id}"
            value = session_model.model_dump_json()

            await redis_client.setex(key, ttl, value)

            logger.debug(f"채팅 세션 저장: user_id={user_id}, ttl={ttl}s")
            return True

        except Exception as e:
            logger.error(f"채팅 세션 저장 실패: {e}")
            return False

    async def get_chat_session(self, user_id: str) -> Optional[Dict]:
        """
        AI 채팅 세션 조회

        Args:
            user_id: 사용자 ID

        Returns:
            채팅 세션 데이터 (dict) 또는 None
        """
        try:
            redis_client = await self.client.get_client()

            key = f"{self.chat_prefix}{user_id}"
            value = await redis_client.get(key)

            if not value:
                logger.debug(f"채팅 세션 없음: user_id={user_id}")
                return None

            session_model = ChatSessionData.model_validate_json(value)
            chat_data = session_model.model_dump()

            logger.debug(f"채팅 세션 조회 성공: user_id={user_id}")

            return chat_data

        except Exception as e:
            logger.error(f"채팅 세션 조회 실패: {e}")
            return None

    async def delete_chat_session(self, user_id: str) -> bool:
        """
        AI 채팅 세션 삭제

        Args:
            user_id: 사용자 ID
        """
        try:
            redis_client = await self.client.get_client()

            key = f"{self.chat_prefix}{user_id}"
            result = await redis_client.delete(key)

            if result > 0:
                logger.info(f"채팅 세션 삭제 성공: user_id={user_id}")
                return True
            else:
                logger.warning(f"삭제할 채팅 세션 없음: user_id={user_id}")
                return False

        except Exception as e:
            logger.error(f"채팅 세션 삭제 실패: {e}")
            return False

    async def refresh_chat_session(self, user_id: str, ttl: int = 1800) -> bool:
        """
        AI 채팅 세션 TTL 갱신

        Args:
            user_id: 사용자 ID
            ttl: 새로운 만료 시간 (초, 기본 30분)
        """
        try:
            redis_client = await self.client.get_client()

            key = f"{self.chat_prefix}{user_id}"
            result = await redis_client.expire(key, ttl)

            if result:
                logger.debug(f"채팅 세션 TTL 갱신: user_id={user_id}, ttl={ttl}s")
                return True
            else:
                logger.warning(f"갱신할 채팅 세션 없음: user_id={user_id}")
                return False

        except Exception as e:
            logger.error(f"채팅 세션 갱신 실패: {e}")
            return False

    async def exists_chat_session(self, user_id: str) -> bool:
        """
        AI 채팅 세션 존재 여부 확인

        Args:
            user_id: 사용자 ID
        """
        try:
            redis_client = await self.client.get_client()

            key = f"{self.chat_prefix}{user_id}"
            result = await redis_client.exists(key)

            return result > 0

        except Exception as e:
            logger.error(f"채팅 세션 존재 확인 실패: {e}")
            return False