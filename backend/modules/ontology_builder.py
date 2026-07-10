"""Ontology builder: rule draft first, then one LLM semantic enhancement."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from backend.ai.llm_service import LLMService, env_bool, llm_group_max_records, robust_json_parse
from backend.config import settings
from backend.modules.document_structure_analyzer import analyze_document_structure
from backend.modules.llm_context_compressor import build_rule_draft_enhancement_context, compress_records_for_llm
from backend.modules.ontology_global_merger import merge_ontology_programmatically
from backend.modules.ontology_stats import count_ontology_stats
from backend.modules.ontology_validator import build_rule_draft_properties, validate_and_complete_ontology


PROMPT_VERSION = "rule_draft_llm_enhance_v3_coded_classes_reference_relations"
CACHE_ROOT = settings.DATA_DIR / "cache"
ONTOLOGY_CACHE_DIR = CACHE_ROOT / "ontology"
ENHANCE_CACHE_DIR = CACHE_ROOT / "llm_enhance"


def build_ontology(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return _finalize(_empty_ontology(), "rule_only", ["Invalid ontology input."], _empty_stats(), LLMService())
    options = _options(payload)
    if options["mode"] == "group_llm":
        return build_ontology_with_llm_groups(payload)
    return build_ontology_with_rule_draft_llm_enhance(payload)


def build_ontology_with_rule_draft_llm_enhance(state: Dict[str, Any]) -> Dict[str, Any]:
    start = time.perf_counter()
    options = _options(state)
    clean_data = state.get("clean_data") if "clean_data" in state else state
    clean_data = clean_data if isinstance(clean_data, dict) else {}
    records = clean_data.get("records", []) if isinstance(clean_data.get("records", []), list) else []
    raw_text = str(clean_data.get("raw_text") or clean_data.get("clean_text") or state.get("raw_text") or "")
    source_doc = str(state.get("file_path") or clean_data.get("source_file") or "")
    progress = state.get("progress_callback")
    service = LLMService(timeout=options["llm_single_call_timeout"], max_retries=0)
    warnings: List[str] = []
    stats = _empty_stats()

    if not records:
        raise RuntimeError("DATA_EXTRACTION_FAILED: 未从 PDF 中提取到结构化教育标准表格数据。")

    document_structure = analyze_document_structure(clean_data, raw_text)
    _progress(progress, "rule_draft", "规则生成初始本体中")
    rule_draft = rule_draft_ontology(records, document_structure, source_doc=source_doc)
    stats.update({
        "generation_strategy": "rule_draft_llm_enhance",
        "total_records": len(records),
        "record_groups": len(document_structure.get("detected_groups", []) or []),
        **_validation_stats(rule_draft),
    })

    if len(rule_draft.get("datatype_properties", []) or []) == 0:
        raise RuntimeError("ONTOLOGY_VALIDATION_FAILED: records>0 但规则草稿 datatype_properties=0。")

    if options["mode"] == "rule_only":
        _progress(progress, "validate", "本体规则校验补全中", stats=stats)
        ontology = validate_and_complete_ontology(rule_draft, records, document_structure, source_doc=source_doc)
        stats.update(_validation_stats(ontology))
        stats["duration_ms"] = _elapsed_ms(start)
        return _finalize(ontology, "rule_only", warnings, stats, service, source_docs=[source_doc])

    _progress(progress, "context_compress", "LLM 上下文压缩中", stats=stats)
    context = build_rule_draft_enhancement_context(clean_data, document_structure, rule_draft)
    final_cache_path = ONTOLOGY_CACHE_DIR / f"{_final_cache_key(state, clean_data, context, service, options)}.json"
    if options["enable_cache"] and not options["force_regenerate"] and final_cache_path.exists():
        cached = _read_json(final_cache_path)
        if cached and cached.get("datatype_properties"):
            cached["stats"] = {**cached.get("stats", {}), **count_ontology_stats(cached), "cache_hit": True}
            cached["stats"]["duration_ms"] = _elapsed_ms(start)
            return cached

    enhancement: Dict[str, Any] = {}
    generation_mode = "rule_draft_llm_enhance"
    enhance_cache_path = ENHANCE_CACHE_DIR / f"{_hash_json({'context': context, 'model': service.model, 'prompt_version': PROMPT_VERSION})}.json"
    if options["enable_cache"] and not options["force_regenerate"] and enhance_cache_path.exists():
        enhancement = _read_json(enhance_cache_path)
        stats["enhance_cache_hit"] = bool(enhancement)
        stats["blueprint_cache_hit"] = bool(enhancement)

    if options["mode"] == "smoke_llm":
        enhancement = _smoke_llm(service, stats, warnings, progress)
        generation_mode = "smoke_llm"
    elif not service.available:
        warnings.append("LLM API key is not configured; using rule draft fallback.")
        generation_mode = "llm_timeout_fallback"
    elif not enhancement:
        llm_start = time.perf_counter()
        try:
            _progress(progress, "llm_enhance", "大模型语义增强中", stats={"llm_calls": 1})
            response = service.chat_completion(
                [{"role": "user", "content": _rule_draft_llm_enhance_prompt(context)}],
                temperature=0.1,
                json_mode=True,
                max_tokens=800,
                timeout=45,
            )
            enhancement = robust_json_parse(response.get("content", ""))
            stats.update({
                "llm_calls": 1,
                "llm_enhance_success": True,
                "llm_blueprint_success": True,
                "content_extract_ok": bool(response.get("content_extract_ok", True)),
                "llm_duration_ms": _elapsed_ms(llm_start),
            })
            if options["enable_cache"]:
                _write_json(enhance_cache_path, enhancement)
        except Exception as exc:
            stats.update({
                "llm_calls": 1,
                "llm_enhance_success": False,
                "llm_blueprint_success": False,
                "content_extract_ok": False,
                "llm_duration_ms": _elapsed_ms(llm_start),
                "llm_error_type": str(getattr(exc, "error_type", type(exc).__name__)),
            })
            warnings.append(f"LLM enhancement failed fast; using rule draft. error_type={stats['llm_error_type']}: {exc}")
            generation_mode = "llm_timeout_fallback" if "Timeout" in stats["llm_error_type"] else "llm_failed_fallback"
    else:
        stats["llm_enhance_success"] = True
        stats["llm_blueprint_success"] = True

    if options["enable_review"] and generation_mode == "rule_draft_llm_enhance":
        generation_mode = "rule_draft_llm_enhance_review"
        warnings.append("LLM review is disabled by default; no extra review call was made.")

    _progress(progress, "apply_enhancement", "应用大模型增强结果中", stats=stats)
    ontology = apply_llm_enhancement_to_rule_draft(rule_draft, enhancement)

    _progress(progress, "validate", "本体规则校验补全中", stats=stats)
    ontology = validate_and_complete_ontology(ontology, records, document_structure, source_doc=source_doc)
    if len(ontology.get("datatype_properties", []) or []) == 0:
        raise RuntimeError("ONTOLOGY_VALIDATION_FAILED: records>0 但 datatype_properties=0。")

    stats.update(_validation_stats(ontology))
    stats["duration_ms"] = _elapsed_ms(start)
    stats["timeout_reached"] = stats["duration_ms"] > options["max_generation_seconds"] * 1000
    if stats["timeout_reached"] and generation_mode == "rule_draft_llm_enhance":
        generation_mode = "partial_llm_timeout"
        warnings.append("Generation exceeded max_generation_seconds; returning validated current result.")
    if stats.get("object_properties", 0) == 0:
        warnings.append("object_properties is 0; OWL export will still include classes, datatype properties, and hierarchy.")

    result = _finalize(ontology, generation_mode, warnings, stats, service, source_docs=[source_doc])
    if options["enable_cache"] and generation_mode not in {"llm_failed_fallback", "llm_timeout_fallback"}:
        _write_json(final_cache_path, result)
    return result


def rule_draft_ontology(records: list, document_structure: dict, source_doc: str = "") -> dict:
    classes = _rule_classes(records, document_structure)
    coded_hierarchy = _coded_class_hierarchy(records)
    reference_relations = _reference_relations(records)
    ontology = {
        "classes": classes,
        "datatype_properties": build_rule_draft_properties(records, classes, source_doc=source_doc),
        "properties": [],
        "object_properties": _object_property_candidates(records, classes),
        "relations": reference_relations,
        "class_hierarchy": [
            *[{"parent": "EducationResource", "child": cls["id"], "generated_by": "rule_draft"}
              for cls in classes if cls.get("id") not in {"EducationResource", "EducationDataElement"}],
            *coded_hierarchy,
        ],
        "alignment_hints": [],
    }
    ontology["properties"] = ontology["datatype_properties"]
    ontology["source_mappings"] = _source_mappings(ontology)
    ontology["validation"] = {
        "rule_completed_properties": 0,
        "datatype_properties_by_llm_rules": 0,
        "rule_draft_properties": len(ontology["datatype_properties"]),
        "source_mapped_elements": len(ontology["source_mappings"]),
    }
    return ontology


def _coded_class_hierarchy(records: list) -> list[dict]:
    relations = []
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        child, parent, _, _ = _standard_class_from_record(record)
        if not child or not parent or (parent, child) in seen:
            continue
        seen.add((parent, child))
        relations.append({"parent": parent, "child": child, "generated_by": "standard_code_hierarchy"})
    return relations


def _reference_relations(records: list) -> list[dict]:
    """Create traceable object relations from standard reference numbers."""
    import re

    relations = []
    seen = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        source_class, _, _, _ = _standard_class_from_record(record)
        reference = str(record.get("reference") or record.get("reference_id") or "")
        for target_code in re.findall(r"\b[A-Z]{4}\d{6}\b", reference.upper()):
            target_class, _, _, _ = _standard_class_from_record({"code": target_code})
            if not source_class or not target_class or source_class == target_class:
                continue
            key = (source_class, "referencesDataElement", target_class)
            if key in seen:
                continue
            seen.add(key)
            source_code = str(record.get("code") or record.get("id") or "")
            relations.append({
                "subject": source_class,
                "source": source_class,
                "predicate": "referencesDataElement",
                "type": "referencesDataElement",
                "object": target_class,
                "target": target_class,
                "label": "引用数据元素",
                "description": "由标准数据项的引用编号推导。",
                "source_record_ids": [str(record.get("id") or record.get("code") or f"record_{index + 1}")],
                "source_code": source_code,
                "target_code": target_code,
                "evidence": [f"{source_code} -> {target_code}"],
                "generated_by": "reference_number",
            })
    return relations


def apply_llm_enhancement_to_rule_draft(rule_draft_ontology: dict, llm_enhancement: dict) -> dict:
    base = json.loads(json.dumps(rule_draft_ontology, ensure_ascii=False))
    enhancement = llm_enhancement if isinstance(llm_enhancement, dict) else {}
    base["classes"] = _merge_by_id(base.get("classes", []), [], "class")
    class_ids = {_safe_class_id(item.get("id") or item.get("name") or item.get("label")) for item in base["classes"] if isinstance(item, dict)}
    if not class_ids:
        class_ids = {"EducationResource"}
        base["classes"] = [{"id": "EducationResource", "name": "EducationResource", "label": "Education Resource", "generated_by": "rule_draft"}]

    object_props = _limit_dicts(enhancement.get("object_properties", []), 8, ("id", "name", "label", "domain", "range"))
    relations = _limit_dicts(enhancement.get("relations", []), 8, ("subject", "source", "predicate", "type", "object", "target"))
    base["object_properties"] = _dedupe_dicts([*(base.get("object_properties", []) or []), *object_props], ("domain", "id", "name", "range"))
    base["relations"] = _dedupe_dicts([*(base.get("relations", []) or []), *relations], ("subject", "source", "predicate", "type", "object", "target"))
    base["alignment_hints"] = []
    base["warnings"] = [str(item)[:160] for item in (enhancement.get("warnings", []) if isinstance(enhancement.get("warnings", []), list) else [])[:3]]
    base["properties"] = base.get("datatype_properties", [])
    base["source_mappings"] = _source_mappings(base)
    return base


def build_ontology_with_llm_groups(state: Dict[str, Any]) -> Dict[str, Any]:
    clean_data = state.get("clean_data") if "clean_data" in state else state
    records = clean_data.get("records", []) if isinstance(clean_data, dict) and isinstance(clean_data.get("records", []), list) else []
    raw_text = str(clean_data.get("clean_text") or clean_data.get("raw_text") or state.get("raw_text") or "") if isinstance(clean_data, dict) else ""
    document_structure = analyze_document_structure(clean_data if isinstance(clean_data, dict) else {}, raw_text)
    groups = compress_records_for_llm(records, document_structure, _options(state)["max_group_records"])
    draft = rule_draft_ontology(records, document_structure, source_doc=str(state.get("file_path") or ""))
    result = validate_and_complete_ontology(merge_ontology_programmatically([draft]), records, document_structure, source_doc=str(state.get("file_path") or ""))
    stats = {**_empty_stats(), **_validation_stats(result), "total_records": len(records), "record_groups": len(groups), "generation_strategy": "group_llm"}
    return _finalize(result, "group_llm", ["group_llm currently preserves rule draft and skips default extra LLM batches."], stats, LLMService(), source_docs=[str(state.get("file_path") or "")])


def _rule_draft_llm_enhance_prompt(context: dict) -> str:
    schema = {
        "object_properties": [],
        "relations": [],
        "warnings": [],
    }
    return (
        "Return strict JSON only. No markdown. You are doing a tiny semantic enhancement for an education ontology. "
        "Use only ids/classes shown in context. Do not output datatype_properties, classes, hierarchy, corrections, descriptions, or long evidence. "
        "Limits: object_properties<=8, relations<=8, warnings<=3. Each object_property only needs id,label,domain,range. "
        "Each relation only needs subject,predicate,object.\n"
        f"JSON schema: {json.dumps(schema, ensure_ascii=False)}\n"
        f"Context: {json.dumps(context, ensure_ascii=False, separators=(',', ':'))}"
    )


def _smoke_llm(service: LLMService, stats: dict, warnings: list, progress: Any) -> dict:
    start = time.perf_counter()
    try:
        _progress(progress, "llm_enhance", "大模型语义增强中", stats={"llm_calls": 1})
        response = service.chat_completion([{"role": "user", "content": "{\"warnings\": []}"}], temperature=0.0, json_mode=True, max_tokens=100, timeout=45)
        stats.update({"llm_calls": 1, "llm_enhance_success": True, "content_extract_ok": True, "llm_duration_ms": _elapsed_ms(start)})
        return robust_json_parse(response.get("content", "{}"))
    except Exception as exc:
        stats.update({"llm_calls": 1, "llm_enhance_success": False, "content_extract_ok": False, "llm_duration_ms": _elapsed_ms(start), "llm_error_type": str(getattr(exc, "error_type", type(exc).__name__))})
        warnings.append(f"smoke_llm failed: {exc}")
        return {}


def _rule_classes(records: list, document_structure: dict) -> list:
    """Build classes from the standard's coded data-class hierarchy.

    A data-element code in these education standards has the form
    ``ABCD010301``: the first four digits identify the data class/subclass
    (``ABCD0103``), while the final two digits identify the field.  The old
    implementation only used a small, generic candidate-domain template
    (Student/School/Teacher...), which made unrelated documents repeatedly
    produce the same 34 classes.  Keep those generic domains only as a
    fallback; coded classes are the primary, traceable source of ontology
    classes.
    """
    class_ids = {"EducationResource", "EducationDataElement"}
    class_labels = {
        "EducationResource": "教育资源",
        "EducationDataElement": "教育数据元素",
    }
    for record in records:
        if not isinstance(record, dict):
            continue
        class_id, group_id, class_label, group_label = _standard_class_from_record(record)
        if class_id:
            class_ids.add(class_id)
            class_labels[class_id] = class_label
            if group_id:
                class_ids.add(group_id)
                class_labels[group_id] = group_label

        # Referenced elements may be defined only in another standard file.
        # Add their classes so cross-standard reference relations remain valid.
        for reference_relation in _reference_relations([record]):
            target_code = reference_relation["target_code"]
            target_id, target_group, target_label, target_group_label = _standard_class_from_record({"code": target_code})
            if target_id:
                class_ids.add(target_id)
                class_labels[target_id] = target_label
            if target_group:
                class_ids.add(target_group)
                class_labels[target_group] = target_group_label

    for group in document_structure.get("detected_groups", []) if isinstance(document_structure, dict) else []:
        for name in group.get("possible_entities", []) if isinstance(group, dict) else []:
            class_ids.add(_safe_class_id(name) or "EducationDataElement")
    for record in records:
        if isinstance(record, dict):
            for name in record.get("candidate_domains", []) if isinstance(record.get("candidate_domains"), list) else []:
                class_ids.add(_safe_class_id(name) or "EducationDataElement")
    classes = [
        {"id": cid, "name": cid, "label": class_labels.get(cid, cid), "generated_by": "rule_draft"}
        for cid in sorted(class_ids)
    ]
    return classes


def _standard_class_from_record(record: dict) -> tuple[str, str, str, str]:
    """Return subclass and data-set identifiers encoded in a standard field code."""
    import re

    code = re.sub(r"\s+", "", str(record.get("code") or record.get("id") or "")).upper()
    match = re.match(r"^([A-Z]{4})(\d{4})\d{2}$", code)
    if not match:
        return "", "", "", ""
    prefix, hierarchy_code = match.groups()
    class_code = f"{prefix}{hierarchy_code}"
    group_code = f"{prefix}{hierarchy_code[:2]}"
    return (
        f"DataClass{class_code}",
        f"DataSet{group_code}",
        f"数据子类 {class_code}",
        f"数据类 {group_code}",
    )


def _object_property_candidates(records: list, classes: list) -> list:
    class_ids = {item["id"] for item in classes if isinstance(item, dict) and item.get("id")}
    if "EducationResource" in class_ids and "EducationDataElement" in class_ids:
        return [{
            "id": "hasDataElement",
            "name": "hasDataElement",
            "label": "has data element",
            "domain": "EducationResource",
            "range": "EducationDataElement",
            "generated_by": "rule_draft",
            "evidence": ["rule draft relation between resource and data elements"],
        }]
    return []


def _source_mappings(ontology: dict) -> list:
    mappings = []
    for element_type in ("classes", "datatype_properties", "object_properties", "relations"):
        for item in ontology.get(element_type, []) if isinstance(ontology.get(element_type, []), list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("source_doc") or item.get("source_record_ids") or item.get("evidence"):
                mappings.append({
                    "element_type": element_type,
                    "element_id": item.get("id") or item.get("name") or item.get("label"),
                    "source_doc": item.get("source_doc", ""),
                    "source_record_ids": item.get("source_record_ids", []),
                    "source_table": item.get("source_table", ""),
                    "evidence": item.get("evidence", []),
                })
    return mappings


def _merge_by_id(left: list, right: list, generated_by: str) -> list:
    result = [item for item in left if isinstance(item, dict)]
    index = {_safe_class_id(item.get("id") or item.get("name") or item.get("label")).lower(): item for item in result}
    for item in right if isinstance(right, list) else []:
        if not isinstance(item, dict):
            continue
        key = _safe_class_id(item.get("id") or item.get("name") or item.get("label"))
        if not key:
            continue
        if key.lower() in index:
            index[key.lower()].update({k: v for k, v in item.items() if v not in (None, "", [])})
        else:
            result.append({**item, "id": key, "name": key, "generated_by": item.get("generated_by") or generated_by})
    return result


def _finalize(ontology: dict, generation_mode: str, warnings: List[str], stats: dict, service: LLMService, source_docs: Optional[List[str]] = None) -> dict:
    validation = ontology.get("validation", {}) if isinstance(ontology, dict) else {}
    stats = {**_empty_stats(), **stats, **_count_stats(ontology)}
    stats["generation_mode"] = generation_mode
    stats["generation_strategy"] = stats.get("generation_strategy") or "rule_draft_llm_enhance"
    stats["rule_draft_properties"] = int(validation.get("rule_draft_properties", stats.get("rule_draft_properties", 0)) or 0)
    stats["source_mapped_elements"] = int(validation.get("source_mapped_elements", stats.get("source_mapped_elements", 0)) or 0)
    stats["source_mappings"] = len(ontology.get("source_mappings", []) or []) or stats["source_mapped_elements"]
    stats["alignment_mappings"] = len(ontology.get("alignment_mappings", []) or [])
    all_warnings = _dedupe_text([*warnings, *(ontology.get("warnings", []) if isinstance(ontology.get("warnings", []), list) else [])])
    metadata = {
        "generation_mode": generation_mode,
        "generation_strategy": stats["generation_strategy"],
        "llm_provider": service.provider,
        "llm_model": service.model,
        "prompt_version": PROMPT_VERSION,
        "source_docs": [doc for doc in (source_docs or []) if doc],
        "alignment_strategy": "rule_alignment_with_llm_hints",
        "cache_hit": bool(stats.get("cache_hit")),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    return {
        "classes": ontology.get("classes", []),
        "properties": ontology.get("datatype_properties") or ontology.get("properties", []),
        "datatype_properties": ontology.get("datatype_properties") or ontology.get("properties", []),
        "object_properties": ontology.get("object_properties", []),
        "relations": ontology.get("relations", []),
        "class_hierarchy": ontology.get("class_hierarchy", []),
        "alignment_hints": ontology.get("alignment_hints", []),
        "source_mappings": ontology.get("source_mappings", []),
        "alignment_mappings": ontology.get("alignment_mappings", []),
        "metadata": metadata,
        "stats": stats,
        "warnings": all_warnings,
    }


def _empty_stats() -> dict:
    return {
        "generation_mode": "",
        "generation_strategy": "",
        "total_records": 0,
        "record_groups": 0,
        "llm_calls": 0,
        "llm_enhance_success": False,
        "llm_blueprint_success": False,
        "llm_review_success": False,
        "content_extract_ok": True,
        "llm_duration_ms": 0,
        "llm_error_type": "",
        "classes": 0,
        "datatype_properties": 0,
        "object_properties": 0,
        "relations": 0,
        "rule_draft_properties": 0,
        "datatype_properties_by_llm_rules": 0,
        "aligned_ontology_count": 1,
        "alignment_mappings": 0,
        "source_mappings": 0,
        "source_mapped_elements": 0,
        "cache_hit": False,
        "enhance_cache_hit": False,
        "blueprint_cache_hit": False,
        "duration_ms": 0,
        "timeout_reached": False,
        "warnings": [],
    }


def _validation_stats(ontology: dict) -> dict:
    validation = ontology.get("validation", {}) if isinstance(ontology, dict) else {}
    return {
        **_count_stats(ontology),
        "rule_draft_properties": int(validation.get("rule_draft_properties", 0) or 0),
        "datatype_properties_by_llm_rules": int(validation.get("datatype_properties_by_llm_rules", 0) or 0),
        "source_mapped_elements": int(validation.get("source_mapped_elements", 0) or 0),
        "source_mappings": len(ontology.get("source_mappings", []) or []) or int(validation.get("source_mapped_elements", 0) or 0),
    }


def _count_stats(ontology: dict) -> dict:
    return count_ontology_stats(ontology)


def _options(state: dict) -> dict:
    opts = state.get("generate_options", {}) if isinstance(state, dict) else {}
    mode = _normalize_mode(str(opts.get("mode") or "rule_draft_llm_enhance"))
    return {
        "mode": mode,
        "force_regenerate": bool(opts.get("force_regenerate", False)),
        "max_group_records": int(opts.get("max_group_records") or llm_group_max_records()),
        "enable_review": bool(opts.get("enable_review", False)) or mode == "rule_draft_llm_enhance_review",
        "enable_alignment": bool(opts.get("enable_alignment", True)),
        "enable_deep_alignment": bool(opts.get("enable_deep_alignment", False)),
        "enable_global_merge": bool(opts.get("enable_global_merge", False)),
        "enable_cache": bool(opts.get("enable_cache", env_bool("ENABLE_LLM_CACHE", True))),
        "max_generation_seconds": int(opts.get("max_generation_seconds") or 180),
        "llm_single_call_timeout": int(opts.get("llm_single_call_timeout") or 45),
    }


def _normalize_mode(mode: str) -> str:
    aliases = {
        "llm_fast": "rule_draft_llm_enhance",
        "llm_blueprint": "rule_draft_llm_enhance",
        "llm_blueprint_review": "rule_draft_llm_enhance_review",
        "llm_deep": "group_llm",
        "full_llm": "group_llm",
    }
    return aliases.get(mode, mode or "rule_draft_llm_enhance")


def _final_cache_key(state: dict, clean_data: dict, context: dict, service: LLMService, options: dict) -> str:
    return _hash_json({
        "source_file_hash": _file_hash(state.get("file_path")),
        "structured_file_hash": _file_hash(state.get("structured_file")),
        "clean_data_hash": _hash_json(clean_data),
        "context_hash": _hash_json(context),
        "llm_model": service.model,
        "prompt_version": PROMPT_VERSION,
        "mode": options["mode"],
    })


def _safe_class_id(value: Any) -> str:
    import re
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    if not text:
        return ""
    return "".join(part[:1].upper() + part[1:] for part in text.split("_") if part)


def _dedupe_dicts(items: list, keys: tuple[str, ...]) -> list:
    seen = set()
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        marker = tuple(str(item.get(key) or "").lower() for key in keys if item.get(key))
        if not marker:
            marker = (json.dumps(item, ensure_ascii=False, sort_keys=True)[:160],)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def _limit_dicts(items: Any, limit: int, allowed_keys: tuple[str, ...]) -> list:
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        compact = {key: item.get(key) for key in allowed_keys if item.get(key)}
        if compact:
            result.append(compact)
        if len(result) >= limit:
            break
    return result


def _file_hash(path_value: Any) -> str:
    try:
        path = Path(str(path_value or ""))
        if path.exists() and path.is_file():
            h = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
    except OSError:
        pass
    return ""


def _hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _progress(callback: Any, step: str, label: str, message: str = "", stats: Optional[dict] = None) -> None:
    if callable(callback):
        callback(step, label, message=message or label, stats=stats or {})


def _dedupe_text(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _empty_ontology() -> Dict[str, Any]:
    return {"classes": [], "properties": [], "datatype_properties": [], "object_properties": [], "relations": [], "class_hierarchy": []}




