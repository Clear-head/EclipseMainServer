class AuthException(Exception):
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InvalidCredentialsException(AuthException):
    def __init__(self, message: str = "아이디 또는 비밀번호가 올바르지 않습니다."):
        super().__init__(message, status_code=401)


class UserNotFoundException(AuthException):
    def __init__(self, message: str = "사용자를 찾을 수 없습니다."):
        super().__init__(message, status_code=404)


class UserAlreadyExistsException(AuthException):
    def __init__(self, message: str = "이미 존재하는 사용자입니다."):
        super().__init__(message, status_code=409)


class InvalidTokenException(AuthException):
    def __init__(self, message: str = "유효하지 않은 토큰입니다."):
        super().__init__(message, status_code=401)


class ExpiredAccessTokenException(AuthException):
    def __init__(self, message: str = "토큰이 만료되었습니다."):
        super().__init__(message, status_code=401)

class ExpiredRefreshTokenException(AuthException):
    def __init__(self, message: str = "토큰이 만료되었습니다."):
        super().__init__(message, status_code=401)


class MissingTokenException(AuthException):
    def __init__(self, message: str = "인증 토큰이 필요합니다."):
        super().__init__(message, status_code=401)


class InvalidHeaderException(AuthException):
    def __init__(self, message: str = "헤더가 올바르지 않습니다."):
        super().__init__(message, status_code=400)


class WeakPasswordException(AuthException):
    def __init__(self, message: str = "비밀번호는 8자 이상이어야 합니다."):
        super().__init__(message, status_code=400)


class InvalidEmailException(AuthException):
    def __init__(self, message: str = "올바른 이메일 형식이 아닙니다."):
        super().__init__(message, status_code=400)


class DuplicateUserInfoError(AuthException):
    def __init__(self, msg="유저 정보 중복 존재"):
        self.msg = msg
        super().__init__(self.msg, status_code=400)