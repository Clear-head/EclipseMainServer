class ServiceException(Exception):
    def __init__(self, message: str, traceback=None):
        self.message = message
        self.traceback = traceback
        super().__init__(message)

