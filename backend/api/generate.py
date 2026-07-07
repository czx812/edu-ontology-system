import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from config import settings
from core.workflow import ModuleNotReadyError, run_workflow
from services.log_service import write_generation_record, write_operation_log, write_system_log


router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    file_path: str


def generate_ontology(file_path: str, user: dict) -> dict:
    export_dir = settings.EXPORT_DIR / str(user["id"])
    export_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    write_system_log("INFO", f"本体生成开始：{file_path}")

    try:
        state = run_workflow({"file_path": file_path, "export_dir": str(export_dir)})
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        clean_data = state.get("clean_data", {}) if isinstance(state.get("clean_data", {}), dict) else {}
        record_count = int(clean_data.get("record_count", 0) or 0)
        structured_file = state.get("structured_file", "")
        owl_file = state.get("owl_file", "")
        write_generation_record(
            user=user,
            file_name=Path(file_path).name,
            file_path=file_path,
            structured_file=structured_file,
            record_count=record_count,
            owl_file=owl_file,
            status="SUCCESS",
            duration_ms=duration_ms,
        )
        write_operation_log(
            user=user,
            action="GENERATE_ONTOLOGY",
            method="POST",
            path="/generate",
            status_code=200,
            duration_ms=duration_ms,
            detail=f"生成成功，record_count = {record_count}，owl_file = {owl_file}",
        )
        write_system_log("INFO", f"本体生成成功：{file_path}")
        return {
            "message": "本体生成成功",
            "ontology": state.get("ontology", {}),
            "structured_file": structured_file,
            "record_count": record_count,
            "owl_file": owl_file,
            "errors": state.get("errors", []),
            "generation_record": {"status": "SUCCESS", "duration_ms": duration_ms},
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        write_generation_record(
            user=user,
            file_name=Path(file_path).name,
            file_path=file_path,
            status="FAILED",
            error_message=str(exc),
            duration_ms=duration_ms,
        )
        write_operation_log(
            user=user,
            action="GENERATE_ONTOLOGY",
            method="POST",
            path="/generate",
            status_code=500,
            duration_ms=duration_ms,
            detail=f"生成失败，错误信息：{exc}",
        )
        write_system_log("ERROR", f"本体生成失败：{exc}")
        raise


@router.post("/generate")
def generate(request: GenerateRequest, user: dict = Depends(get_current_user)) -> dict:
    try:
        result = generate_ontology(request.file_path, user)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ModuleNotReadyError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成失败：{exc}") from exc

    return {**result, "status": "success"}
