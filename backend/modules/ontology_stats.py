from __future__ import annotations

import re
from typing import Any


def count_ontology_stats(ontology: dict) -> dict[str, int]:
    """Count ontology elements with one de-duplicated object-relation basis."""
    ontology = ontology if isinstance(ontology, dict) else {}
    datatype = ontology.get("datatype_properties") or ontology.get("properties") or []
    relation_keys = _relation_keys_from_object_properties(ontology.get("object_properties") or [])
    relation_keys |= _relation_keys_from_relations(ontology.get("relations") or [])
    return {
        "classes": len(_class_keys(ontology.get("classes") or [])),
        "datatype_properties": len(_datatype_property_keys(datatype)),
        "object_properties": len(relation_keys),
        "relations": len(relation_keys),
    }


def _class_keys(items: Any) -> set[str]:
    keys: set[str] = set()
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            key = _safe_class_name(item.get("id") or item.get("name") or item.get("label")).lower()
            if key:
                keys.add(key)
    return keys


def _datatype_property_keys(items: Any) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        domain = _safe_class_name(item.get("domain") or "EducationResource").lower()
        name = _safe_property_name(item.get("id") or item.get("name") or item.get("label")).lower()
        if name:
            keys.add((domain, name))
    return keys


def _relation_keys_from_object_properties(items: Any) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        source = _safe_class_name(item.get("domain") or item.get("source") or item.get("subject")).lower()
        relation_type = _safe_property_name(item.get("id") or item.get("name") or item.get("predicate") or item.get("type")).lower()
        target = _safe_class_name(item.get("range") or item.get("target") or item.get("object")).lower()
        if source and relation_type and target:
            keys.add((source, relation_type, target))
    return keys


def _relation_keys_from_relations(items: Any) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        source = _safe_class_name(item.get("source") or item.get("subject")).lower()
        relation_type = _safe_property_name(item.get("type") or item.get("predicate") or item.get("relation")).lower()
        target = _safe_class_name(item.get("target") or item.get("object")).lower()
        if source and relation_type and target:
            keys.add((source, relation_type, target))
    return keys


def _safe_class_name(value: Any) -> str:
    text = _safe_identifier(value)
    if not text:
        return ""
    return "".join(part[:1].upper() + part[1:] for part in text.split("_") if part)


def _safe_property_name(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"\b([A-Z]{2,}[A-Z0-9]*\d{4,})\b", text, flags=re.I)
    if match:
        return match.group(1).lower()
    return _safe_identifier(value).lower()[:100]


def _safe_identifier(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")
    return re.sub(r"_+", "_", text)
