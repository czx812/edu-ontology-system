from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.auth import get_current_user
from config import settings
from services.log_service import write_operation_log, write_system_log


router = APIRouter(tags=["export"])


def export_owl(file_path: str, user_id: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        path = settings.EXPORT_DIR / str(user_id) / path.name
    if not path.exists():
        path = settings.EXPORT_DIR / path.name
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"OWL文件不存在：{file_path}")
    if path.suffix.lower() != ".owl":
        raise ValueError("只能导出 .owl 文件")
    return {"download_url": str(path)}


@router.get("/export")
def export(file_path: str, user: dict = Depends(get_current_user)):
    try:
        result = export_owl(file_path, user["id"])
        path = Path(result["download_url"])
        write_operation_log(user=user, action="EXPORT_OWL", method="GET", path="/export", status_code=200, detail=f"导出 OWL 文件：{path}")
        write_system_log("INFO", f"OWL 导出成功：{path}")
        return FileResponse(
            path=path,
            filename=path.name,
            media_type="application/octet-stream",
        )
    except FileNotFoundError as exc:
        write_operation_log(user=user, action="EXPORT_OWL", method="GET", path="/export", status_code=404, detail=str(exc))
        write_system_log("ERROR", f"OWL 导出失败：{exc}")
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        write_operation_log(user=user, action="EXPORT_OWL", method="GET", path="/export", status_code=400, detail=str(exc))
        write_system_log("ERROR", f"OWL 导出失败：{exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
