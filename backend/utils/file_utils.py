import hashlib
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
TEMP_PDF_DIR = BASE_DIR / "data" / "temp_pdf"

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("edu_ontology")
logger.success = logger.info


def check_pdf_suffix(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def save_temp_file(file, original_name: str) -> str:
    TEMP_PDF_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(original_name).name
    save_path = TEMP_PDF_DIR / safe_name
    with save_path.open("wb") as f:
        f.write(file.read())
    return str(save_path)


def read_file_bytes(file_path: str) -> bytes:
    with open(file_path, "rb") as f:
        return f.read()


def calc_md5(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def safe_remove(path: str) -> None:
    try:
        target = Path(path)
        if target.exists() and target.is_file():
            target.unlink()
    except OSError as exc:
        logger.warning("????????: %s", exc)


def clear_expired_pdf(days=7):
    import time

    if not TEMP_PDF_DIR.exists():
        return

    now = time.time()
    for path in TEMP_PDF_DIR.iterdir():
        if path.is_file() and path.stat().st_mtime < now - days * 86400:
            path.unlink()
