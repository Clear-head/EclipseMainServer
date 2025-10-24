class LoginFailException(Exception):
    def __init__(self, value=None, msg="아이디 혹은 비밀번호 불일치"):
        self.value = value
        self.msg = msg
        super().__init__(self.msg)


class DuplicateUserInfoError(Exception):
    def __init__(self, value=None, msg="유저 정보 중복 존재"):
        self.value = value
        self.msg = msg
        super().__init__(self.msg)