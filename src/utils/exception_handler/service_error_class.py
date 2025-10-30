class ServiceException(Exception):
    def __init__(self, message: str, traceback=None):
        self.message = message
        self.traceback = traceback
        super().__init__(message)

class NotFoundAnyItemException(ServiceException):
    def __init__(self, message: str = "목록이 존재 하지 않습니다.", traceback=None):
        super().__init__(message, traceback)