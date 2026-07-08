from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from config import settings
from core.workflow import DataExtractionFailedError, ModuleNotReadyError, OntologyValidationFailedError, run_workflow
from services.llm_service import LLMService
from services.log_service import write_generation_record, write_operation_log, write_system_log


router = APIRouter(tags=["generate"])

GENERATION_STEPS = [
    ("pdf_parse", "PDF 解析中"),
    ("data_clean", "数据清洗中"),
    ("schema_match", "模式匹配中"),
    ("rule_draft", "规则生成初始本体中"),
    ("context_compress", "LLM 上下文压缩中"),
    ("llm_enhance", "大模型语义增强中"),
    ("apply_enhancement", "应用大模型增强结果中"),
    ("validate", "本体规则校验补全中"),
    ("align", "多本体对齐中"),
    ("provenance", "数据溯源中"),
    ("owl_export", "OWL 导出中"),
    ("done", "完成"),
]
STEP_INDEX = {step: index + 1 for index, (step, _) in enumerate(GENERATION_STEPS)}
STEP_LABEL = dict(GENERATION_STEPS)
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


class GenerateRequest(BaseModel):
    file_path: str
    mode: str = "rule_draft_llm_enhance"
    force_regenerate: bool = False
    max_group_records: int = 80
    enable_review: bool = False
    enable_alignment: bool = True
    enable_deep_alignment: bool = False
    enable_global_merge: bool = False
    enable_cache: bool = True
    max_generation_seconds: int = 180
    llm_single_call_timeout: int = 45


def _default_stats() -> dict:
    return {
        "generation_mode": "rule_draft_llm_enhance",
        "generation_strategy": "rule_draft_llm_enhance",
        "total_records": 0,
        "datatype_properties": 0,
        "classes": 0,
        "object_properties": 0,
        "relations": 0,
        "source_mappings": 0,
        "alignment_mappings": 0,
        "llm_calls": 0,
        "llm_duration_ms": 0,
        "cache_hit": False,
        "enhance_cache_hit": False,
    }


def generate_ontology(request: GenerateRequest, user: dict, job_id: str | None = None) -> dict:
    file_path = request.file_path
    export_dir = settings.EXPORT_DIR / str(user["id"])
    export_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    LLMService(timeout=request.llm_single_call_timeout, max_retries=1)
    write_system_log("INFO", f"本体生成开始：{file_path}")

    def progress(step: str, label: str, message: str = "", stats: dict | None = None) -> None:
        if job_id:
            _update_job(job_id, step, label, message=message, stats=stats)

    try:
        state = run_workflow({
            "file_path": file_path,
            "export_dir": str(export_dir),
            "progress_callback": progress,
            "generate_options": {
                "mode": request.mode,
                "force_regenerate": request.force_regenerate,
                "max_group_records": request.max_group_records,
                "enable_review": request.enable_review,
                "enable_alignment": request.enable_alignment,
                "enable_deep_alignment": request.enable_deep_alignment,
                "enable_global_merge": request.enable_global_merge,
                "enable_cache": request.enable_cache,
                "max_generation_seconds": request.max_generation_seconds,
                "llm_single_call_timeout": request.llm_single_call_timeout,
            },
        })
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        clean_data = state.get("clean_data", {}) if isinstance(state.get("clean_data", {}), dict) else {}
        record_count = int(clean_data.get("record_count", clean_data.get("records_count", 0)) or len(clean_data.get("records", []) or []))
        ontology = state.get("ontology", {}) if isinstance(state.get("ontology", {}), dict) else {}
        datatype_properties = ontology.get("datatype_properties") or ontology.get("properties") or []
        if record_count == 0:
            raise DataExtractionFailedError("DATA_EXTRACTION_FAILED: 未从 PDF 中提取到结构化教育标准表格数据。")
        if len(datatype_properties) == 0:
            raise OntologyValidationFailedError("ONTOLOGY_VALIDATION_FAILED: records>0 但 datatype_properties=0。")

        stats = ontology.get("stats", {}) if isinstance(ontology.get("stats", {}), dict) else {}
        warnings = ontology.get("warnings", []) if isinstance(ontology.get("warnings", []), list) else []
        generation_mode = ontology.get("metadata", {}).get("generation_mode") or stats.get("generation_mode") or request.mode
        stats["duration_ms"] = stats.get("duration_ms") or duration_ms
        stats["warnings"] = warnings

        response_status = "partial_success" if generation_mode == "llm_timeout_fallback" else "success"
        record_status = "PARTIAL_SUCCESS" if response_status == "partial_success" else "SUCCESS"
        result = {
            "message": "本体生成完成",
            "status": response_status,
            "ontology": ontology,
            "structured_file": state.get("structured_file", ""),
            "record_count": record_count,
            "trace_map": state.get("trace_map", {}),
            "trace_file": state.get("trace_file", ""),
            "owl_file": state.get("owl_file", ""),
            "errors": state.get("errors", []),
            "generation_record": {"status": record_status, "duration_ms": duration_ms},
        }

        write_generation_record(user=user, file_name=Path(file_path).name, file_path=file_path, structured_file=result["structured_file"], record_count=record_count, owl_file=result["owl_file"], status=record_status, duration_ms=duration_ms)
        write_operation_log(user=user, action="GENERATE_ONTOLOGY", method="POST", path="/generate", status_code=200, duration_ms=duration_ms, detail=f"生成完成：mode={generation_mode}, record_count={record_count}, owl_file={result['owl_file']}")
        write_system_log("INFO", f"本体生成成功：{file_path}")
        if job_id:
            message = "完成" if response_status == "success" else "规则初始本体已生成，大模型轻量增强超时，当前为规则兜底结果。"
            _update_job(job_id, "done", STEP_LABEL["done"], message=message, stats=stats, warnings=warnings, status="success")
            with JOBS_LOCK:
                JOBS[job_id]["progress_percent"] = 100
                JOBS[job_id]["result"] = result
        return result
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status_text, generation_mode = _failure_status(exc)
        write_generation_record(user=user, file_name=Path(file_path).name, file_path=file_path, status=status_text, error_message=str(exc), duration_ms=duration_ms)
        write_operation_log(user=user, action="GENERATE_ONTOLOGY", method="POST", path="/generate", status_code=500, duration_ms=duration_ms, detail=f"生成失败：{exc}")
        write_system_log("ERROR", f"本体生成失败：{exc}")
        if job_id:
            _update_job(job_id, "done", STEP_LABEL["done"], message=status_text, stats={"duration_ms": duration_ms, "generation_mode": generation_mode}, warnings=[str(exc)], status="failed")
            with JOBS_LOCK:
                JOBS[job_id]["error"] = str(exc)
        raise


def _failure_status(exc: Exception) -> tuple[str, str]:
    text = str(exc)
    if isinstance(exc, DataExtractionFailedError) or "DATA_EXTRACTION_FAILED" in text:
        return "DATA_EXTRACTION_FAILED", "data_extraction_failed"
    if isinstance(exc, OntologyValidationFailedError) or "ONTOLOGY_VALIDATION_FAILED" in text:
        return "ONTOLOGY_VALIDATION_FAILED", "ontology_validation_failed"
    return "FAILED", "generation_failed"


def _new_job(user: dict, request: GenerateRequest) -> dict:
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "user_id": user["id"],
        "request": request,
        "status": "pending",
        "current_step": "pdf_parse",
        "current_step_label": STEP_LABEL["pdf_parse"],
        "progress_percent": 0,
        "step_index": 1,
        "total_steps": len(GENERATION_STEPS),
        "start_time": time.perf_counter(),
        "elapsed_seconds": 0,
        "message": "等待开始",
        "stats": _default_stats(),
        "warnings": [],
        "result": None,
        "error": "",
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    return job


def _snapshot(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "current_step": job["current_step"],
        "current_step_label": job["current_step_label"],
        "progress_percent": job["progress_percent"],
        "step_index": job["step_index"],
        "total_steps": job["total_steps"],
        "elapsed_seconds": round(time.perf_counter() - job["start_time"], 2),
        "message": job.get("message", ""),
        "stats": job.get("stats", {}),
        "warnings": job.get("warnings", []),
        "error": job.get("error", ""),
    }


def _update_job(job_id: str, step: str, label: str | None = None, message: str = "", stats: dict | None = None, warnings: list | None = None, status: str | None = None) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        index = STEP_INDEX.get(step, job.get("step_index", 1))
        job["current_step"] = step
        job["current_step_label"] = label or STEP_LABEL.get(step, step)
        job["step_index"] = index
        job["progress_percent"] = min(100, round((index - 1) / (len(GENERATION_STEPS) - 1) * 100))
        if message:
            job["message"] = message
        if stats:
            job.setdefault("stats", {}).update(stats)
        if warnings:
            job["warnings"] = _dedupe([*job.get("warnings", []), *warnings])
        if status:
            job["status"] = status


def _assert_job(job_id: str, user: dict) -> dict:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id 不存在")
    if job["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="无权访问该生成任务")
    return job


def _run_job(job_id: str, request: GenerateRequest, user: dict) -> None:
    _update_job(job_id, "pdf_parse", STEP_LABEL["pdf_parse"], message="开始生成", status="running")
    try:
        generate_ontology(request, user, job_id=job_id)
    except Exception:
        pass


@router.post("/generate/start")
def generate_start(request: GenerateRequest, user: dict = Depends(get_current_user)) -> dict:
    job = _new_job(user, request)
    thread = threading.Thread(target=_run_job, args=(job["job_id"], request, dict(user)), daemon=True)
    thread.start()
    return _snapshot(job)


@router.get("/generate/progress/{job_id}")
def generate_progress(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    return _snapshot(_assert_job(job_id, user))


@router.get("/generate/result/{job_id}")
def generate_result(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    job = _assert_job(job_id, user)
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job.get("error") or "生成失败")
    if job["status"] != "success" or not job.get("result"):
        raise HTTPException(status_code=202, detail="任务尚未完成")
    return job["result"]


@router.post("/generate")
def generate(request: GenerateRequest, user: dict = Depends(get_current_user)) -> dict:
    try:
        return generate_ontology(request, user)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DataExtractionFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OntologyValidationFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModuleNotReadyError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except RuntimeError as exc:
        status, _ = _failure_status(exc)
        raise HTTPException(status_code=422 if status != "FAILED" else 400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成失败：{exc}") from exc


def _dedupe(items: list) -> list:
    seen = set()
    result = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
