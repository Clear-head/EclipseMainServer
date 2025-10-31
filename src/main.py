from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.router.users import user_controller, service_controller, my_info_controller
from src.utils.exception_handler.http_log_handler import setup_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):

    yield
app = FastAPI(lifespan=lifespan)
setup_exception_handlers(app)
app.include_router(user_controller.router)
app.include_router(my_info_controller.router)
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