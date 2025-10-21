from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):

    yield

app = FastAPI(lifespan=lifespan)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)