import bcrypt
from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


def hash_password(password: str) -> str:
    try:
        password_bytes = password.encode('utf-8')

        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)

        return hashed.decode('utf-8')

    except Exception as e:
        logger.error(f"비밀번호 해시화 실패: {e}")
        raise e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')

        return bcrypt.checkpw(password_bytes, hashed_bytes)

    except Exception as e:
        logger.error(f"비밀번호 검증 실패: {e}")
        return False