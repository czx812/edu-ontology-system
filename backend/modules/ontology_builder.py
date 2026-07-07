"""Build ontology JSON from structured records or semantic classification output."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from modules.semantic_classifier import semantic_classify

MAX_RECORDS_FOR_ONTOLOGY = 50
MAX_RAW_TEXT_FALLBACK = 3000


def build_ontology(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build an ontology, preferring clean_data.records over raw PDF text."""
    if not isinstance(payload, dict):
        return _empty_ontology()

    semantic_data = _semantic_input(payload)
    if not _looks_classified(semantic_data):
        semantic_data = semantic_classify(semantic_data)

    classes = _dedupe_classes(semantic_data.get("classes", []))
    class_names = {item["name"] for item in classes}

    properties = _dedupe_properties(semantic_data.get("properties", []))
    for prop in properties:
        domain = prop.get("domain") or "EducationResource"
        if domain not in class_names:
            classes.append({
                "name": domain,
                "label": domain,
                "description": "Inferred property domain.",
            })
            class_names.add(domain)

    relations = _dedupe_relations(semantic_data.get("relations", []))
    for relation in relations:
        for endpoint in (relation.get("source"), relation.get("target")):
            if endpoint and endpoint not in class_names:
                classes.append({
                    "name": endpoint,
                    "label": endpoint,
                    "description": "Inferred relation endpoint.",
                })
                class_names.add(endpoint)

    return {
        "classes": classes,
        "properties": properties,
        "relations": relations,
    }


def _semantic_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    if _looks_classified(payload):
        return payload

    clean_data = payload.get("clean_data", {}) if isinstance(payload.get("clean_data", {}), dict) else {}
    records = clean_data.get("records", []) if isinstance(clean_data.get("records", []), list) else []
    if records:
        limited_records = records[:MAX_RECORDS_FOR_ONTOLOGY]
        print(f"[本体构建] 使用结构化记录 {len(limited_records)} 条生成本体")
        return {"clean_data": {**clean_data, "records": limited_records}, "entity_json": {}}

    if "semantic_model" in payload and isinstance(payload.get("semantic_model"), dict):
        return payload["semantic_model"]

    raw_text = str(payload.get("raw_text") or clean_data.get("unstructured_text") or "")
    raw_text = raw_text[:MAX_RAW_TEXT_FALLBACK]
    if raw_text:
        print("[本体构建] records 为空，使用截断 raw_text fallback")
        from ai.entity_extractor import extract_entities

        entity_json = extract_entities({"clean_text": raw_text, "records": []})
        return {"entity_json": entity_json, "clean_data": {"records": []}}

    return {"classes": [], "properties": [], "relations": []}


def _looks_classified(data: Dict[str, Any]) -> bool:
    return any(key in data for key in ("classes", "properties", "relations"))


def _dedupe_classes(items: Any) -> List[Dict[str, str]]:
    seen = set()
    result: List[Dict[str, str]] = []
    for item in _as_dicts(items):
        name = _text(item.get("name") or item.get("label"))
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        result.append({
            "name": name,
            "label": _text(item.get("label")) or name,
            "description": _text(item.get("description")),
        })
    return result


def _dedupe_properties(items: Any) -> List[Dict[str, str]]:
    seen = set()
    result: List[Dict[str, str]] = []
    for item in _as_dicts(items):
        name = _text(item.get("name") or item.get("label"))
        domain = _text(item.get("domain")) or "EducationResource"
        marker = (domain.lower(), name.lower())
        if not name or marker in seen:
            continue
        seen.add(marker)
        result.append({
            "name": name,
            "label": _text(item.get("label")) or name,
            "domain": domain,
            "range": _text(item.get("range")) or "string",
            "description": _text(item.get("description")),
        })
    return result


def _dedupe_relations(items: Any) -> List[Dict[str, str]]:
    seen = set()
    result: List[Dict[str, str]] = []
    for item in _as_dicts(items):
        source = _text(item.get("source") or item.get("subject"))
        target = _text(item.get("target") or item.get("object"))
        rel_type = _text(item.get("type") or item.get("predicate") or item.get("relation"))
        marker = (source.lower(), rel_type.lower(), target.lower())
        if not all(marker) or marker in seen:
            continue
        seen.add(marker)
        result.append({
            "source": source,
            "target": target,
            "type": rel_type,
            "label": _text(item.get("label")) or rel_type,
            "description": _text(item.get("description")),
        })
    return result


def _as_dicts(items: Any) -> Iterable[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _empty_ontology() -> Dict[str, Any]:
    return {"classes": [], "properties": [], "relations": []}
