import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.logger.custom_logger import get_logger
from src.utils.exception_handler.auth_error_class import AuthException

logger = get_logger(__name__)

def setup_exception_handlers(app: FastAPI):

    @app.exception_handler(AuthException)
    async def auth_exception_handler(request: Request, exc: AuthException):
        logger.error(f"Auth error: {exc.message} - Path: {request.url.path}")
        logger.error(traceback.format_exc())

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "headers": {
                    "content_type": "application/json",
                    "jwt": None
                },
                "body": {
                    "status_code": exc.status_code,
                    "message": exc.message
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.error(f"Validation error: {exc.errors()} - Path: {request.url.path}")
        logger.error(traceback.format_exc())

        errors = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            errors.append(f"{field}: {error['msg']}")

        return JSONResponse(
            status_code=422,
            content={
                "headers": {
                    "content_type": "application/json",
                    "jwt": None
                },
                "body": {
                    "status_code": 422,
                    "message": f"Request format error\n{', '.join(errors)}"
                }
            }
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.error(f"HTTP error {exc.status_code}: {exc.detail} - Path: {request.url.path}")
        logger.error("\n===================" + traceback.format_exc() + "\n===================")

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "headers": {
                    "content_type": "application/json",
                    "jwt": None
                },
                "body": {
                    "status_code": exc.status_code,
                    "message": exc.detail
                }
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error("=" * 60)
        logger.error(f"Path: {request.url.path}")
        logger.error(f"Method: {request.method}")
        logger.error(f"Client: {request.client.host if request.client else 'unknown'}")
        logger.error(f"Error Type: {type(exc).__name__}")
        logger.error(f"Error Message: {str(exc)}")
        logger.error("Full Traceback:")
        logger.error(traceback.format_exc())
        logger.error("=" * 60)

        return JSONResponse(
            status_code=500,
            content={
                "headers": {
                    "content_type": "application/json",
                    "jwt": None
                },
                "body": {
                    "status_code": 500,
                    "message": "알수 없는 오류"
                }
            }
        )