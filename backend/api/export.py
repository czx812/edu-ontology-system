from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


router = APIRouter(tags=["export"])


def export_owl(file_path: str) -> dict:
    """
    输出OWL下载路径
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"OWL文件不存在：{file_path}")
    if path.suffix.lower() != ".owl":
        raise ValueError("只能导出 .owl 文件")
    return {"download_url": str(path)}


@router.get("/export")
def export(file_path: str):
    try:
        result = export_owl(file_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    path = Path(result["download_url"])
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/octet-stream",
    )
