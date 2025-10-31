import os
import traceback
from datetime import datetime, timedelta, timezone

import jwt as jwt_token
from dotenv import load_dotenv
from fastapi import Header

from src.logger.custom_logger import get_logger
from src.utils.exception_handler.auth_error_class import InvalidTokenException, MissingTokenException, \
    ExpiredAccessTokenException
from src.utils.path import path_dic

path = path_dic["env"]
load_dotenv(path)
public_key = os.environ.get("PUBLIC_KEY")
algorithm = "HS256"
logger = get_logger(__name__)

async def create_jwt_token(username: str) -> tuple:

    now = (datetime.now(timezone.utc))
    access_token_expires = now + timedelta(hours=1)
    refresh_token_expires = now + timedelta(hours=15)

    now = int(now.timestamp())
    access_token_expires = int(access_token_expires.timestamp())
    refresh_token_expires = int(refresh_token_expires.timestamp())

    payload = {
        "username": username,                           #   유저 이름
        "exp": access_token_expires,                    #   만료 시간
        "iat": now,                                     #   생성 시간
        "iss": os.environ.get("ISSUE_NAME")             #   서명
    }

    #   refresh token
    payload2 = {
        "username": username,
        "exp": refresh_token_expires,
        "iat": now,
        "iss": os.environ.get("ISSUE_NAME")
    }

    token1 = jwt_token.encode(payload, public_key, algorithm=algorithm)
    token2 = jwt_token.encode(payload2, public_key, algorithm=algorithm)

    return token1, token2


async def validate_jwt_token(jwt: str = Header(None)):

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

        #   todo: 여기에 유저네임이 세션에 없을 때 추가

        else:
            return True

    except jwt_token.ExpiredSignatureError as e:
        logger.error(type(e).__name__ + str(e))
        traceback.print_exc()
        raise ExpiredAccessTokenException()

    except jwt_token.InvalidTokenError as e:
        raise InvalidTokenException() from e
