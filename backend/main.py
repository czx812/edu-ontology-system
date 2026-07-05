from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import api_router


APP_NAME = "教育本体构建系统"
APP_VERSION = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="教育本体构建系统后端服务",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()


@app.get("/")
def root() -> dict:
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}

