from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.infra.cache.redis_connector import RedisConnector, close_redis
from src.router.admin import monitoring_controller, dashboard_controller
from src.router.users import user_controller, my_info_controller, auth_controller, \
    category_controller, history_controller, review_controller, service_controller
from src.service.scheduler.crawling_scheduler import scheduler
from src.utils.exception_handler.http_log_handler import setup_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 스케줄러 실행
    scheduler.start()
    redis_client = RedisConnector()
    await redis_client.connect()
    
    yield
    
    # 종료 시 스케줄러 정리
    scheduler.shutdown()
    await close_redis()


app = FastAPI(lifespan=lifespan)
setup_exception_handlers(app)

# 대시보드 (HTML 파일 및 API 모두 포함)
app.include_router(dashboard_controller.router)

app.include_router(auth_controller.router)
app.include_router(category_controller.router)
app.include_router(user_controller.router)
app.include_router(my_info_controller.router)
app.include_router(service_controller.router)
app.include_router(history_controller.router)
app.include_router(review_controller.router)
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
    uvicorn.run(app, host="0.0.0.0", port=8080)