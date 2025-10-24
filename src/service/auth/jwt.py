import traceback

import jwt
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, timezone

from src.logger.custom_logger import get_logger
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
        "exp": access_token_expires,                #   만료 시간
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

        #   서명 검증 실패
        if decoded["iss"] != os.environ.get("ISSUE_NAME"):
            raise jwt.InvalidTokenError()

        #   토큰 만료 상황
        elif decoded["exp"] < now:
            raise jwt.ExpiredSignatureError()

        #   생성시간 보다 만료시간이 더 이전 일 때
        elif decoded["iat"] > decoded["exp"]:
            print(3)
            return 3

        #   생성시간이 지금보다 미래 일때
        elif decoded["iat"] > now:
            raise jwt.InvalidTokenError()

        else:
            return 1

    except jwt.ExpiredSignatureError as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()
        logger.error(type(e).__name__ + str(e))
        return 2

    except jwt.InvalidTokenError as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()
        logger.error(type(e).__name__ + str(e))
        return 3

    except Exception as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()
        logger.error(type(e).__name__ + str(e))
        return 4


async def get_refill_token(token: str) -> tuple:
    #   받아온 리프레시 토큰 검증
    if validate_jwt_token(token) == 1:
        token1, token2 = await create_jwt_token(token)
        return token1
    else:
        raise jwt.InvalidTokenError()
