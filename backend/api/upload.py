from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile

from config import settings


router = APIRouter(tags=["upload"])


def _safe_pdf_name(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="只能上传 PDF 文件")
    return f"{uuid4().hex}.pdf"


def upload_pdf(file: UploadFile) -> dict:
    """
    输入：PDF文件
    输出：
    {
        "file_path": str
    }
    """
    save_name = _safe_pdf_name(file.filename)
    save_path = settings.UPLOAD_DIR / save_name

    with save_path.open("wb") as target:
        while chunk := file.file.read(1024 * 1024):
            target.write(chunk)

    return {"file_path": save_path.name}


@router.post("/upload")
def upload(file: UploadFile) -> dict:
    return upload_pdf(file)

