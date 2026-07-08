from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List

from backend.ai.llm_service import llm_group_max_records


def build_llm_blueprint_context(clean_data: dict, document_structure: dict) -> dict:
    """Return one compact context for the default blueprint prompt."""
    records = clean_data.get("records", []) if isinstance(clean_data, dict) else []
    detected_groups = []
    sample_records = []

    for group in document_structure.get("detected_groups", [])[:20] if isinstance(document_structure, dict) else []:
        if not isinstance(group, dict):
            continue
        samples = [_compact_sample(item) for item in group.get("sample_records", [])[:3] if isinstance(item, dict)]
        detected_groups.append({
            "group_id": group.get("group_id"),
            "group_title": group.get("group_title"),
            "record_count": group.get("record_count", 0),
            "representative_fields": list(group.get("representative_fields", [])[:5]),
            "field_patterns": list(group.get("field_patterns", [])[:5]),
            "possible_entities": list(group.get("possible_entities", [])[:6]),
            "relation_clues": list(group.get("relation_clues", [])[:5]),
        })
        sample_records.extend(samples)

    if len(sample_records) < 60:
        seen = {item.get("record_id") for item in sample_records}
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            compact = _compact_record(record, index)
            if compact.get("record_id") in seen:
                continue
            sample_records.append(compact)
            seen.add(compact.get("record_id"))
            if len(sample_records) >= 60:
                break

    return {
        "document_title": document_structure.get("document_title") or "Education Ontology Document",
        "total_records": len(records),
        "sections": list(document_structure.get("sections") or document_structure.get("section_hierarchy") or [])[:60],
        "detected_groups": detected_groups[:20],
        "sample_records": sample_records[:60],
    }


def build_rule_draft_enhancement_context(clean_data: dict, document_structure: dict, rule_draft_ontology: dict) -> dict:
    datatype_properties = rule_draft_ontology.get("datatype_properties") or rule_draft_ontology.get("properties") or []
    relation_clues = []
    for group in (document_structure.get("detected_groups", []) or [])[:10] if isinstance(document_structure, dict) else []:
        if not isinstance(group, dict):
            continue
        for clue in group.get("relation_clues", [])[:2]:
            if isinstance(clue, dict):
                relation_clues.append({
                    "record_id": clue.get("record_id"),
                    "text": _clean(clue.get("text"))[:120],
                })
            if len(relation_clues) >= 10:
                break
        if len(relation_clues) >= 10:
            break
    if not relation_clues:
        for clue in (document_structure.get("relation_clues", []) or [])[:10] if isinstance(document_structure, dict) else []:
            if isinstance(clue, dict):
                relation_clues.append({"record_id": clue.get("record_id"), "text": _clean(clue.get("text"))[:120]})
    return {
        "classes": _compact_classes(rule_draft_ontology.get("classes", []), 15),
        "property_samples": _sample_properties(datatype_properties, limit=15),
        "relation_clues": relation_clues[:10],
    }


def compress_records_for_llm(records: list, document_structure: dict, max_group_records: int | None = None) -> list:
    """Legacy grouped context for group_llm mode."""
    max_size = max_group_records or llm_group_max_records()
    buckets: Dict[str, List[dict]] = {}
    for index, record in enumerate(records if isinstance(records, list) else []):
        normalized = _compact_record(record, index)
        if not normalized:
            continue
        key = normalized.get("section_path") or normalized.get("group_title") or "Ungrouped"
        buckets.setdefault(key, []).append(normalized)

    groups = []
    for title, items in buckets.items():
        for chunk_index in range(0, len(items), max_size):
            chunk = items[chunk_index : chunk_index + max_size]
            group_title = title if len(items) <= max_size else f"{title} #{chunk_index // max_size + 1}"
            clues = _clues_for_group(chunk, document_structure)
            group_id = _group_id(group_title, chunk)
            groups.append({
                "group_id": group_id,
                "group_title": group_title,
                "section_path": title,
                "record_count": len(chunk),
                "summary": _summary(group_title, chunk, clues),
                "records": chunk,
                "relation_clues": clues,
            })
    return groups


def _compact_record(record: Any, index: int) -> dict:
    if not isinstance(record, dict):
        return {}
    record_id = _first(record, "id", "code", "record_id", "name") or f"record_{index + 1}"
    name = _first(record, "cn_name", "item_name", "label", "name") or record_id
    description = _first(record, "description", "comment", "explanation")
    if not any(str(v or "").strip() for v in (record_id, name, description)):
        return {}
    return {
        "record_id": str(record_id)[:120],
        "code": str(_first(record, "code", "id") or "")[:120],
        "name": _clean(name)[:180],
        "type": str(_first(record, "data_type", "type", "value_type") or "")[:80],
        "description": _clean(description)[:500],
        "reference_id": str(_first(record, "reference_id", "reference", "ref") or "")[:120],
        "source_page": record.get("source_page") or record.get("page") or "",
        "source_table": str(record.get("source_table") or "")[:180],
        "source_section": str(record.get("source_section") or "")[:180],
        "section_path": str(record.get("source_section") or record.get("source_table") or "Ungrouped")[:180],
        "group_title": str(record.get("source_table") or record.get("source_section") or "Ungrouped")[:180],
    }


def _compact_sample(record: dict) -> dict:
    return {
        "record_id": str(record.get("record_id") or record.get("id") or record.get("code") or "")[:120],
        "code": str(record.get("code") or "")[:120],
        "name": _clean(record.get("name") or record.get("cn_name") or record.get("item_name") or "")[:180],
        "type": str(record.get("type") or record.get("data_type") or "")[:80],
        "description": _clean(record.get("description") or "")[:300],
        "reference_id": str(record.get("reference_id") or record.get("reference") or "")[:120],
    }


def _sample_properties(properties: Any, limit: int = 15) -> List[dict]:
    items = [item for item in properties if isinstance(item, dict)] if isinstance(properties, list) else []
    if len(items) <= limit:
        sample = items
    else:
        head = items[: limit // 2]
        step = max(1, len(items) // (limit // 2))
        tail = items[limit // 2 :: step][: limit - len(head)]
        sample = [*head, *tail]
    return [
        {
            "id": item.get("id"),
            "label": item.get("label"),
            "domain": item.get("domain"),
            "range": item.get("range"),
        }
        for item in sample
    ]


def _compact_classes(items: Any, limit: int) -> List[dict]:
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        result.append({
            "id": item.get("id") or item.get("name"),
            "label": item.get("label") or item.get("name") or item.get("id"),
        })
        if len(result) >= limit:
            break
    return result


def _compact_items(items: Any, limit: int) -> List[dict]:
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        result.append({key: item.get(key) for key in ("id", "name", "label", "domain", "range", "parent", "child", "source_doc", "source_table", "source_record_ids", "evidence") if item.get(key)})
        if len(result) >= limit:
            break
    return result


def _first(record: dict, *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return ""


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clues_for_group(records: List[dict], document_structure: dict) -> List[dict]:
    ids = {str(item.get("record_id") or "") for item in records}
    clues = []
    for clue in document_structure.get("relation_clues", []) if isinstance(document_structure, dict) else []:
        if not isinstance(clue, dict):
            continue
        if not clue.get("record_id") or str(clue.get("record_id")) in ids or clue.get("source") in {r.get("source_table") or r.get("source_section") for r in records}:
            clues.append(clue)
        if len(clues) >= 20:
            break
    return clues


def _summary(title: str, records: List[dict], clues: List[dict]) -> str:
    names = ", ".join(str(item.get("name") or item.get("record_id")) for item in records[:12])
    return f"{title}: {len(records)} records. Main fields: {names}. Relation clues: {len(clues)}."


def _group_id(title: str, records: List[dict]) -> str:
    seed = title + "|" + "|".join(str(item.get("record_id") or "") for item in records)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
