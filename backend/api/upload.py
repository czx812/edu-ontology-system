from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.auth import get_current_user
from config import settings
from services.log_service import write_operation_log, write_system_log


router = APIRouter(tags=["upload"])


def _safe_pdf_name(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="只能上传 PDF 文件")
    return f"{uuid4().hex}.pdf"


def upload_pdf(file: UploadFile, user_id: str) -> dict:
    save_name = _safe_pdf_name(file.filename)
    save_dir = settings.UPLOAD_DIR / str(user_id)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / save_name

    with save_path.open("wb") as target:
        while chunk := file.file.read(1024 * 1024):
            target.write(chunk)

    return {"file_path": str(save_path), "file_name": file.filename or save_name}


@router.post("/upload")
def upload(file: UploadFile, user: dict = Depends(get_current_user)) -> dict:
    try:
        result = upload_pdf(file, user["id"])
        detail = f"上传文件：{file.filename}，保存路径：{result['file_path']}"
        write_operation_log(user=user, action="UPLOAD_PDF", method="POST", path="/upload", status_code=200, detail=detail)
        write_system_log("INFO", f"上传 PDF 成功：{file.filename}")
        return result
    except HTTPException as exc:
        write_operation_log(user=user, action="UPLOAD_PDF", method="POST", path="/upload", status_code=exc.status_code, detail=str(exc.detail))
        write_system_log("ERROR", f"上传 PDF 失败：{exc.detail}")
        raise
    except Exception as exc:
        write_operation_log(user=user, action="UPLOAD_PDF", method="POST", path="/upload", status_code=500, detail=str(exc))
        write_system_log("ERROR", f"上传 PDF 失败：{exc}")
        raise HTTPException(status_code=500, detail=f"上传失败：{exc}") from exc


@router.post("/upload/batch")
def upload_batch(files: list[UploadFile] = File(...), user: dict = Depends(get_current_user)) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No PDF files uploaded")
    results = []
    file_paths = []
    try:
        for file in files:
            result = upload_pdf(file, user["id"])
            path = Path(result["file_path"])
            item = {
                "filename": result.get("file_name") or file.filename or path.name,
                "file_path": result["file_path"],
                "size": path.stat().st_size if path.exists() else 0,
            }
            results.append(item)
            file_paths.append(item["file_path"])
        write_operation_log(user=user, action="BATCH_UPLOAD", method="POST", path="/upload/batch", status_code=200, detail=f"batch_upload count={len(results)}")
        write_system_log("INFO", f"Batch PDF upload success: count={len(results)}")
        return {"file_paths": file_paths, "files": results}
    except HTTPException as exc:
        write_operation_log(user=user, action="BATCH_UPLOAD", method="POST", path="/upload/batch", status_code=exc.status_code, detail=str(exc.detail))
        raise
    except Exception as exc:
        write_operation_log(user=user, action="BATCH_UPLOAD", method="POST", path="/upload/batch", status_code=500, detail=str(exc))
        write_system_log("ERROR", f"Batch PDF upload failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {exc}") from exc

