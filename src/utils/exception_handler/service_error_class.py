class ServiceException(Exception):
    def __init__(self, message: str, status_code: int = 401, trace_back: str = None):
        self.message = message
        self.status_code = status_code
        self.trace_back = trace_back
        super().__init__(self.message)

class NotFoundAnyItemException(ServiceException):
    def __init__(self, message: str = "목록이 존재 하지 않습니다.", status_code: int = 404, traceback=None):
        super().__init__(message, status_code)