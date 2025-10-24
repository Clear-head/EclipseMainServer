from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from starlette.middleware.cors import CORSMiddleware

from src.logger.http_log_handler import setup_exception_handlers
from src.router.users import user_controller, service_controller


@asynccontextmanager
async def lifespan(app: FastAPI):

    yield
app = FastAPI()
setup_exception_handlers(app)
app = FastAPI(lifespan=lifespan)
app.include_router(user_controller.router)
app.include_router(service_controller.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)