from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.modules.ontology_stats import count_ontology_stats


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return _text(value).lower()


def _source_files(item: dict) -> list[str]:
    result: list[str] = []
    for source in _sources(item):
        value = source.get("file_path") or source.get("source_file") or source.get("filename")
        if value and str(value) not in result:
            result.append(str(value))
    for key in ("source_file", "source_doc"):
        value = item.get(key)
        if value and str(value) not in result:
            result.append(str(value))
    return result


def _sources(item: dict) -> list[dict]:
    sources = item.get("sources") if isinstance(item.get("sources"), list) else []
    source = item.get("source") if isinstance(item.get("source"), dict) else None
    result = [s for s in sources if isinstance(s, dict)]
    if source:
        result.append(source)
    return _dedupe_sources(result)


def merge_ontologies(local_ontologies: list[dict], alignment_result: dict) -> dict:
    ontologies = [item for item in local_ontologies if isinstance(item, dict)]
    warnings: list[str] = []
    classes = _merge_classes(ontologies)
    properties = _merge_properties(ontologies, warnings)
    object_properties = _merge_object_properties(ontologies)
    relations = _merge_relations(ontologies)
    source_files = _all_source_files(ontologies)
    alignment_result = alignment_result if isinstance(alignment_result, dict) else {}
    metadata = {
        "generation_mode": "batch_merged",
        "source_file_count": len(source_files),
        "source_files": source_files,
        "local_stats": [item.get("stats", {}) for item in ontologies],
        "alignment_stats": {
            "class_mappings": len(alignment_result.get("class_mappings", []) or []),
            "property_mappings": len(alignment_result.get("property_mappings", []) or []),
            "relation_mappings": len(alignment_result.get("relation_mappings", []) or []),
        },
    }
    stats = {
        **count_ontology_stats({
            "classes": classes,
            "datatype_properties": properties,
            "object_properties": object_properties,
            "relations": relations,
        }),
        "properties": len(properties),
        "source_files": len(source_files),
    }
    return {
        "classes": classes,
        "properties": properties,
        "datatype_properties": properties,
        "object_properties": object_properties,
        "relations": relations,
        "class_hierarchy": _merge_hierarchy(ontologies),
        "alignment": alignment_result,
        "metadata": metadata,
        "stats": stats,
        "warnings": [*warnings, *(alignment_result.get("warnings", []) or [])],
    }


def _merge_classes(ontologies: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for ontology in ontologies:
        source_files = _ontology_sources(ontology)
        for item in ontology.get("classes", []) or []:
            if not isinstance(item, dict):
                continue
            name = _text(item.get("id") or item.get("name") or item.get("label"))
            if not name or _looks_like_code(name):
                continue
            key = _norm(name)
            if key not in by_key:
                by_key[key] = {**item, "id": name, "name": name, "source_files": []}
            by_key[key]["source_files"] = _dedupe_text([*by_key[key].get("source_files", []), *source_files])
    return list(by_key.values())


def _merge_properties(ontologies: list[dict], warnings: list[str]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for ontology in ontologies:
        ontology_sources = _ontology_sources(ontology)
        for prop in ontology.get("datatype_properties") or ontology.get("properties") or []:
            if not isinstance(prop, dict):
                continue
            code = _text(prop.get("code") or prop.get("source_code") or prop.get("id") or prop.get("name"))
            key = _norm(code) if code else _norm(prop.get("label") or prop.get("name"))
            if not key:
                continue
            if key not in by_key:
                merged = {**prop}
                merged["code"] = code or prop.get("code", "")
                merged["sources"] = _sources(prop)
                merged["source_files"] = _dedupe_text([*_source_files(prop), *ontology_sources])
                by_key[key] = merged
                continue
            target = by_key[key]
            for field in ("field_name", "label", "data_type", "length", "constraint", "description", "range", "domain"):
                if not target.get(field) and prop.get(field):
                    target[field] = prop.get(field)
                elif target.get(field) and prop.get(field) and str(target.get(field)) != str(prop.get(field)) and field in {"data_type", "length", "constraint", "range"}:
                    warnings.append(f"Property conflict for {code or key}: {field}={target.get(field)} / {prop.get(field)}")
            target["sources"] = _dedupe_sources([*target.get("sources", []), *_sources(prop)])
            target["source_files"] = _dedupe_text([*target.get("source_files", []), *_source_files(prop), *ontology_sources])
    return list(by_key.values())


def _merge_object_properties(ontologies: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str, str], dict] = {}
    for ontology in ontologies:
        sources = _ontology_sources(ontology)
        for item in ontology.get("object_properties", []) or []:
            if not isinstance(item, dict):
                continue
            key = (_norm(item.get("domain") or item.get("source")), _norm(item.get("id") or item.get("type") or item.get("predicate")), _norm(item.get("range") or item.get("target")))
            if key not in by_key:
                by_key[key] = {**item, "source_files": sources}
            else:
                by_key[key]["source_files"] = _dedupe_text([*by_key[key].get("source_files", []), *sources])
    return list(by_key.values())


def _merge_relations(ontologies: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str, str], dict] = {}
    for ontology in ontologies:
        sources = _ontology_sources(ontology)
        for item in ontology.get("relations", []) or []:
            if not isinstance(item, dict):
                continue
            key = (_norm(item.get("source") or item.get("subject")), _norm(item.get("type") or item.get("predicate")), _norm(item.get("target") or item.get("object")))
            if not all(key):
                continue
            if key not in by_key:
                by_key[key] = {**item, "source_files": sources}
            else:
                by_key[key]["source_files"] = _dedupe_text([*by_key[key].get("source_files", []), *sources])
    return list(by_key.values())


def _merge_hierarchy(ontologies: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for ontology in ontologies:
        for item in ontology.get("class_hierarchy", []) or []:
            if not isinstance(item, dict):
                continue
            key = (_norm(item.get("parent")), _norm(item.get("child")))
            if key in seen or not all(key):
                continue
            seen.add(key)
            result.append(item)
    return result


def _ontology_sources(ontology: dict) -> list[str]:
    metadata = ontology.get("metadata", {}) if isinstance(ontology, dict) else {}
    docs = metadata.get("source_docs") if isinstance(metadata.get("source_docs"), list) else []
    return _dedupe_text([str(item) for item in docs if item])


def _all_source_files(ontologies: list[dict]) -> list[str]:
    result = []
    for ontology in ontologies:
        result.extend(_ontology_sources(ontology))
    return _dedupe_text(result)


def _dedupe_sources(items: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        key = (item.get("file_path") or item.get("source_file"), item.get("page"), item.get("table_index"), item.get("row_index"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_text(items: list[Any]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        text = _text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _looks_like_code(value: str) -> bool:
    text = _text(value)
    return bool(text and any(ch.isdigit() for ch in text) and len(text) >= 8 and text.upper() == text)


