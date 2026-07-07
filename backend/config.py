from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
STRUCTURED_DIR = DATA_DIR / "structured"

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


settings = Settings()

for directory in (
    settings.DATA_DIR,
    settings.UPLOAD_DIR,
    settings.EXPORT_DIR,
    settings.STRUCTURED_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)
