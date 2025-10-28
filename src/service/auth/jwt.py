import traceback

import jwt
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, timezone

from src.logger.custom_logger import get_logger
from src.utils.exception_handler.auth_error_class import InvalidTokenException
from src.utils.path import path_dic

path = path_dic["env"]
load_dotenv(path)
public_key = os.environ.get("PUBLIC_KEY")
algorithm = "HS256"
logger = get_logger(__name__)

async def create_jwt_token(username: str) -> tuple:

    now = (datetime.now(timezone.utc))
    access_token_expires = now + timedelta(seconds=2)
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

    token1 = jwt.encode(payload, public_key, algorithm=algorithm)
    token2 = jwt.encode(payload2, public_key, algorithm=algorithm)

    return token1, token2


async def validate_jwt_token(jwt_token: str) -> int:
    try:
        now = int(datetime.now(timezone.utc).timestamp())
        decoded = jwt.decode(jwt_token, public_key, algorithms=algorithm)

        #   위조된 토큰
        if (
                decoded["iss"] != os.environ.get("ISSUE_NAME")      #   서명 에러
                or decoded["iat"] > decoded["exp"]                  #   만료일자 < 생성일자
                or decoded["iat"] > now                             #   생성일자 > 지금
        ):
            raise jwt.InvalidTokenError()

        #   토큰 만료 상황
        elif decoded["exp"] < now:
            raise jwt.ExpiredSignatureError()

        #   todo: 여기에 유저네임이 세션에 없을 때 추가

        else:
            return 1

    except jwt.ExpiredSignatureError as e:
        logger.error(type(e).__name__ + str(e))
        traceback.print_exc()
        return 2

    except jwt.InvalidTokenError as e:
        raise InvalidTokenException() from e
