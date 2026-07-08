import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent
for path in (CURRENT_DIR, PROJECT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api.admin_logs import router as admin_logs_router
from api.auth import router as auth_router
from api.export import router as export_router
from api.generate import router as generate_router
from api.logs import router as logs_router
from api.upload import router as upload_router
from config import settings
from middleware.log_middleware import RequestLogMiddleware
from services.log_service import init_log_tables, write_system_log


APP_NAME = "教育本体构建系统"
APP_VERSION = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="基于大模型智能体的教育本体构建系统",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLogMiddleware)

    for router in (
        auth_router,
        upload_router,
        generate_router,
        export_router,
        logs_router,
        admin_logs_router,
    ):
        app.include_router(router)

    @app.on_event("startup")
    def startup() -> None:
        init_log_tables()
        write_system_log("INFO", "后端服务启动")
        print("[系统] 日志管理模块已启用")
        print(f"[系统] 系统日志文件：{settings.SYSTEM_LOG_FILE}")

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
