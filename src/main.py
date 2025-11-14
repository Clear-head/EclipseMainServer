from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.router.users import user_controller, service_controller, my_info_controller, auth_controller, \
    category_controller
from src.router.admin import monitoring_controller
from src.service.scheduler.crawling_scheduler import scheduler
from src.utils.exception_handler.http_log_handler import setup_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 스케줄러 실행
    scheduler.start()
    
    yield
    
    # 종료 시 스케줄러 정리
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
setup_exception_handlers(app)
app.include_router(auth_controller.router)
app.include_router(category_controller.router)
app.include_router(user_controller.router)
app.include_router(my_info_controller.router)
app.include_router(service_controller.router)
app.include_router(monitoring_controller.router)


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
    uvicorn.run(app, host="0.0.0.0", port=8000)