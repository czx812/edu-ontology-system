from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
STRUCTURED_DIR = DATA_DIR / "structured"
TRACE_DIR = DATA_DIR / "traces"
LOG_DIR = DATA_DIR / "logs"
SYSTEM_LOG_FILE = LOG_DIR / "system.log"
DB_FILE = DATA_DIR / "app.db"

# 读取项目根目录下的 .env
load_dotenv(PROJECT_DIR / ".env")


class Settings:
    APP_NAME = "教育本体构建系统"
    APP_VERSION = "0.1.0"
    CORS_ORIGINS = ["*"]

    BASE_DIR = BASE_DIR
    PROJECT_DIR = PROJECT_DIR
    DATA_DIR = DATA_DIR
    UPLOAD_DIR = UPLOAD_DIR
    EXPORT_DIR = EXPORT_DIR
    STRUCTURED_DIR = STRUCTURED_DIR
    TRACE_DIR = TRACE_DIR
    LOG_DIR = LOG_DIR
    SYSTEM_LOG_FILE = SYSTEM_LOG_FILE
    DB_FILE = DB_FILE


settings = Settings()

for directory in (
    settings.DATA_DIR,
    settings.UPLOAD_DIR,
    settings.EXPORT_DIR,
    settings.STRUCTURED_DIR,
    settings.TRACE_DIR,
    settings.LOG_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)
