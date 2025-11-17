import os
import traceback
from datetime import datetime, timedelta, timezone

import jwt as jwt_token
from dotenv import load_dotenv
from fastapi import Header

from src.infra.cache.redis_connector import get_redis
from src.infra.cache.redis_repository import SessionRepository
from src.logger.custom_logger import get_logger
from src.utils.exception_handler.auth_error_class import InvalidTokenException, MissingTokenException, \
    ExpiredAccessTokenException
from src.utils.path import path_dic

path = path_dic["env"]
load_dotenv(path)
public_key = os.environ.get("PUBLIC_KEY")
algorithm = "HS256"
logger = get_logger(__name__)

async def create_jwt_token(user_id: str) -> tuple:
    session_repo = SessionRepository()

    now = (datetime.now(timezone.utc))
    access_token_expires = now + timedelta(hours=1)
    refresh_token_expires = now + timedelta(hours=15)

    now = int(now.timestamp())
    access_token_expires = int(access_token_expires.timestamp())
    refresh_token_expires = int(refresh_token_expires.timestamp())

    payload = {
        "userId": user_id,                           #   유저 이름
        "exp": access_token_expires,                    #   만료 시간
        "iat": now,                                     #   생성 시간
        "iss": os.environ.get("ISSUE_NAME")             #   서명
    }

    #   refresh token
    payload2 = {
        "userId": user_id,
        "exp": refresh_token_expires,
        "iat": now,
        "iss": os.environ.get("ISSUE_NAME")
    }

    token1 = jwt_token.encode(payload, public_key, algorithm=algorithm)
    token2 = jwt_token.encode(payload2, public_key, algorithm=algorithm)

    access_ttl = int((access_token_expires - now))
    await session_repo.set_session(
        session_id=token1,
        user_id=user_id,
        token_type="access",
        ttl=access_ttl,  # 3600초
        data={"refresh_token": token2}
    )

    refresh_ttl = int((refresh_token_expires - now))
    await session_repo.set_session(
        session_id=token2,
        user_id=user_id,
        token_type="refresh",
        ttl=refresh_ttl,  # 54000초
        data={"access_token": token1}
    )

    return token1, token2


async def get_jwt_user_id(jwt: str = Header(None)) -> str:

    if jwt is None:
        logger.error("Missing token")
        raise MissingTokenException()

    try:
        now = int(datetime.now(timezone.utc).timestamp())
        decoded = jwt_token.decode(jwt, public_key, algorithms=algorithm)

        session_repo = SessionRepository()
        session = await session_repo.get_session(jwt)

        if not session:
            logger.error("no session")
            raise InvalidTokenException()

        #   위조된 토큰
        if (
                decoded["iss"] != os.environ.get("ISSUE_NAME")
                or decoded["iat"] > decoded["exp"]
                or decoded["iat"] > now
        ):
            raise jwt_token.InvalidTokenError()

        #   토큰 만료 상황
        elif decoded["exp"] < now:
            raise jwt_token.ExpiredSignatureError()

        else:
            return decoded["userId"]

    except jwt_token.ExpiredSignatureError as e:
        logger.error(type(e).__name__ + str(e))
        traceback.print_exc()
        raise ExpiredAccessTokenException()

    except jwt_token.InvalidTokenError as e:
        raise InvalidTokenException() from e


async def validate_jwt_token(jwt: str = Header(None)):
    """
        업데이트로 미사용 처리 기록용으로 남겨둠
    """

    if jwt is None:
        logger.error("Missing token")
        raise MissingTokenException()

    try:
        now = int(datetime.now(timezone.utc).timestamp())
        decoded = jwt_token.decode(jwt, public_key, algorithms=algorithm)

        #   위조된 토큰
        if (
                decoded["iss"] != os.environ.get("ISSUE_NAME")      #   서명 에러
                or decoded["iat"] > decoded["exp"]                  #   만료일자 < 생성일자
                or decoded["iat"] > now                             #   생성일자 > 지금
        ):
            raise jwt_token.InvalidTokenError()

        #   토큰 만료 상황
        elif decoded["exp"] < now:
            raise jwt_token.ExpiredSignatureError()

        #   세션에 없음
        elif SessionRepository().get_session(jwt) is None:
            raise jwt_token.InvalidTokenError()

        else:
            return True

    except jwt_token.ExpiredSignatureError as e:
        logger.error(type(e).__name__ + str(e))
        traceback.print_exc()
        raise ExpiredAccessTokenException()

    except jwt_token.InvalidTokenError as e:
        raise InvalidTokenException() from e
