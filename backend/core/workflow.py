import json
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Optional

from config import settings
from modules.ontology_stats import count_ontology_stats


class ModuleNotReadyError(RuntimeError):
    pass


class DataExtractionFailedError(RuntimeError):
    pass


class OntologyValidationFailedError(RuntimeError):
    pass


DEFAULT_STATE = {
    "file_path": "",
    "export_dir": "",
    "raw_text": "",
    "tables": [],
    "clean_data": {},
    "structured_file": "",
    "entity_json": {},
    "semantic_model": {},
    "ontology": {},
    "trace_map": {},
    "trace_file": "",
    "owl_file": "",
    "errors": [],
    "generate_options": {},
}


def _merge_state(state: dict) -> dict:
    merged = DEFAULT_STATE.copy()
    merged.update(state or {})
    return merged


def _load_function(module_name: str, function_name: str) -> Callable[..., Any]:
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ModuleNotReadyError(f"模块还没准备好：{module_name}") from exc

    func = getattr(module, function_name, None)
    if not callable(func):
        raise ModuleNotReadyError(f"函数还没实现：{module_name}.{function_name}()")
    return func


def extract_node(state: dict) -> dict:
    state = _merge_state(state)
    parse_pdf = _load_function("modules.pdf_parser", "parse_pdf")
    return parse_pdf(state)


def clean_node(state: dict) -> dict:
    state = _merge_state(state)
    clean_data = _load_function("modules.data_cleaner", "clean_data")
    return clean_data(state)


def schema_match_node(state: dict) -> dict:
    state = _merge_state(state)
    match_schema = _load_function("modules.schema_matcher", "match_schema")
    state["clean_data"] = match_schema(state.get("clean_data", {}))
    return state


def entity_extract_node(state: dict) -> dict:
    state = _merge_state(state)
    extract_entities = _load_function("ai.entity_extractor", "extract_entities")
    state["entity_json"] = extract_entities(state["clean_data"])
    return state


def semantic_classify_node(state: dict) -> dict:
    state = _merge_state(state)
    semantic_classify = _load_function("modules.semantic_classifier", "semantic_classify")
    state["semantic_model"] = semantic_classify({
        "entity_json": state["entity_json"],
        "clean_data": state["clean_data"],
    })
    return state


def ontology_build_node(state: dict) -> dict:
    state = _merge_state(state)
    build_ontology = _load_function("modules.ontology_builder", "build_ontology")
    state["ontology"] = build_ontology(state)
    return state


def align_node(state: dict) -> dict:
    state = _merge_state(state)
    align_ontology = _load_function("modules.ontology_aligner", "align_ontology")
    state["ontology"] = align_ontology(state["ontology"])
    return state


def provenance_node(state: dict) -> dict:
    state = _merge_state(state)
    build_trace_map = _load_function("modules.provenance", "build_trace_map")
    state["trace_map"] = build_trace_map(state["clean_data"], state["ontology"])
    state["trace_file"] = state["trace_map"].get("trace_file", "")
    return state


def owl_generate_node(state: dict) -> dict:
    state = _merge_state(state)
    ontology = state.get("ontology", {}) if isinstance(state.get("ontology", {}), dict) else {}
    datatype_properties = ontology.get("datatype_properties") or ontology.get("properties") or []
    if not datatype_properties:
        raise OntologyValidationFailedError("ONTOLOGY_VALIDATION_FAILED: records>0 但 datatype_properties=0，停止 OWL 导出。")
    generate_owl = _load_function("modules.owl_generator", "generate_owl")
    export_dir = state.get("export_dir") or str(settings.EXPORT_DIR)
    state["owl_file"] = generate_owl(state["ontology"], export_dir=export_dir)
    return state


def run_workflow(state: dict) -> dict:
    """Full flow: PDF -> parse -> clean -> schema match -> ontology -> align -> provenance -> OWL."""
    state = _merge_state(state)
    file_path = Path(state["file_path"])
    if not file_path.exists():
        file_path = settings.UPLOAD_DIR / file_path.name
    if not file_path.exists():
        raise FileNotFoundError(f"PDF文件不存在：{state['file_path']}")
    state["file_path"] = str(file_path)

    progress = state.get("progress_callback")
    nodes = (
        ("pdf_parse", "PDF 解析中", extract_node),
        ("data_clean", "数据清洗中", clean_node),
        ("schema_match", "模式匹配中", schema_match_node),
        ("rule_draft", "规则生成初始本体中", ontology_build_node),
        ("align", "多本体对齐中", align_node),
        ("provenance", "数据溯源中", provenance_node),
        ("owl_export", "OWL 导出中", owl_generate_node),
    )
    for step, label, node in nodes:
        if callable(progress):
            progress(step, label, message=label)
        state = node(state)
        if step == "schema_match":
            clean_data = state.get("clean_data", {}) if isinstance(state.get("clean_data", {}), dict) else {}
            records = clean_data.get("records", []) if isinstance(clean_data.get("records", []), list) else []
            if len(records) == 0:
                if callable(progress):
                    progress(
                        "done",
                        "完成",
                        message="DATA_EXTRACTION_FAILED: 未从 PDF 中提取到结构化教育标准表格数据。",
                        stats={"generation_mode": "data_extraction_failed", "total_records": 0},
                    )
                raise DataExtractionFailedError("DATA_EXTRACTION_FAILED: 未从 PDF 中提取到结构化教育标准表格数据。")

    return state


def _save_json(data: dict, directory: Path, prefix: str) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = directory / f"{prefix}_{timestamp}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        return str(path.relative_to(settings.PROJECT_DIR)).replace("\\", "/")
    except ValueError:
        return str(path)


def _count_local_result(state: dict, original_filename: str = "") -> dict:
    clean_data = state.get("clean_data", {}) if isinstance(state.get("clean_data", {}), dict) else {}
    ontology = state.get("ontology", {}) if isinstance(state.get("ontology", {}), dict) else {}
    props = ontology.get("datatype_properties") or ontology.get("properties") or []
    stats = count_ontology_stats(ontology)
    return {
        "file_path": state.get("file_path", ""),
        "original_filename": original_filename or Path(str(state.get("file_path") or "")).name,
        "file_name": original_filename or Path(str(state.get("file_path") or "")).name,
        "structured_file": state.get("structured_file", ""),
        "ontology_file": state.get("ontology_file", ""),
        "record_count": int(clean_data.get("record_count") or len(clean_data.get("records", []) or [])),
        "classes": stats["classes"],
        "properties": len(props),
        "relations": stats["relations"],
        "status": "success",
    }


def run_batch_workflow(file_paths: list[str], options: Optional[dict] = None) -> dict:
    options = options or {}
    export_dir = Path(options.get("export_dir") or settings.EXPORT_DIR)
    local_results: list[dict] = []
    local_ontologies: list[dict] = []
    files: list[dict] = []
    warnings: list[str] = []
    upload_names = {
        str(item.get("file_path") or ""): str(item.get("file_name") or item.get("original_filename") or "")
        for item in options.get("file_metadata", [])
        if isinstance(item, dict) and item.get("file_path")
    }

    for file_path in file_paths or []:
        original_filename = upload_names.get(str(file_path), "") or Path(str(file_path)).name
        file_state = {
            "file_path": file_path,
            "export_dir": str(export_dir),
            "generate_options": options,
        }
        file_item = {"file_path": file_path, "filename": original_filename, "status": "pending", "error": ""}
        try:
            state = run_workflow(file_state)
            ontology = state.get("ontology", {}) if isinstance(state.get("ontology", {}), dict) else {}
            ontology_file = _save_json(ontology, export_dir, f"{Path(str(state.get('file_path') or file_path)).stem}_ontology")
            state["ontology_file"] = ontology_file
            file_item.update({
                "raw_text": state.get("raw_text", ""),
                "tables": state.get("tables", []),
                "clean_data": state.get("clean_data", {}),
                "ontology": ontology,
                "structured_file": state.get("structured_file", ""),
                "ontology_file": ontology_file,
                "status": "success",
            })
            local_ontologies.append(ontology)
            local_results.append(_count_local_result(state, original_filename=original_filename))
        except Exception as exc:
            file_item.update({"status": "failed", "error": str(exc)})
            warnings.append(f"{Path(str(file_path)).name}: {exc}")
        files.append(file_item)

    if not local_ontologies:
        raise DataExtractionFailedError("DATA_EXTRACTION_FAILED: batch workflow produced no local ontologies.")

    alignment_result = {"class_mappings": [], "property_mappings": [], "relation_mappings": [], "warnings": []}
    if options.get("enable_alignment", True):
        cross_file_ontology_align = _load_function("modules.batch_ontology_aligner", "cross_file_ontology_align")
        alignment_result = cross_file_ontology_align(local_ontologies)
    alignment_file = _save_json(alignment_result, export_dir, "alignment")

    if options.get("enable_merge", True):
        merge_ontologies = _load_function("modules.ontology_merger", "merge_ontologies")
        merged_ontology = merge_ontologies(local_ontologies, alignment_result)
    else:
        merged_ontology = local_ontologies[0]
    merged_ontology.setdefault("warnings", [])
    merged_ontology["warnings"] = [*merged_ontology.get("warnings", []), *warnings]
    merged_ontology_file = _save_json(merged_ontology, export_dir, "merged_ontology")

    generate_owl = _load_function("modules.owl_generator", "generate_owl")
    owl_file = generate_owl(merged_ontology, export_dir=str(export_dir))
    stats = merged_ontology.get("stats", {}) if isinstance(merged_ontology.get("stats", {}), dict) else {}
    local_summary = {
        "classes": sum(int(item.get("classes") or 0) for item in local_results),
        "properties": sum(int(item.get("properties") or 0) for item in local_results),
        "relations": sum(int(item.get("relations") or 0) for item in local_results),
    }
    merged_summary = {
        "classes": int(stats.get("classes") or 0),
        "properties": int(stats.get("datatype_properties") or stats.get("properties") or 0),
        "relations": int(stats.get("relations") or 0),
    }
    applied_merges = {
        key: max(0, local_summary[key] - merged_summary[key])
        for key in local_summary
    }
    alignment_summary = {
        "candidate_mappings": {
            "classes": len(alignment_result.get("class_mappings", []) or []),
            "properties": len(alignment_result.get("property_mappings", []) or []),
            "relations": len(alignment_result.get("relation_mappings", []) or []),
        },
        # The current merger only removes elements with the same canonical key.
        # These counts are the actual reduction, not the number of candidates.
        "applied_merges": applied_merges,
        "merge_strategy": "canonical_identity_deduplication",
    }
    quality_hints: list[str] = []
    local_class_counts = [int(item.get("classes") or 0) for item in local_results]
    if len(local_class_counts) > 1 and len(set(local_class_counts)) == 1:
        quality_hints.append("多个文件类数量高度一致，请核查是否存在候选类模板化问题。")

    return {
        "status": "success" if not warnings else "partial_success",
        "file_count": len(file_paths or []),
        "local_results": local_results,
        "files": files,
        "local_ontologies": local_ontologies,
        "alignment_result": alignment_result,
        "alignment_file": alignment_file,
        "merged_ontology": merged_ontology,
        "merged_ontology_file": merged_ontology_file,
        "owl_file": owl_file,
        "merged_owl_file_name": Path(owl_file).name,
        "merged_owl_download_url": f"/api/export?file_path={Path(owl_file).name}",
        "merge_status": "success" if options.get("enable_merge", True) else "not_requested",
        "batch_stats": {
            "local": local_summary,
            "merged": merged_summary,
            "reduced": applied_merges,
        },
        "alignment_summary": alignment_summary,
        "quality_hints": quality_hints,
        "merged_stats": stats,
        "stats": stats,
        "warnings": warnings,
    }




