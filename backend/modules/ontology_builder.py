"""Build ontology JSON from semantic classification output."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from modules.semantic_classifier import semantic_classify


def build_ontology(semantic_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build an ontology from semantic classes/properties/relations.

    The builder only accepts concepts already separated by semantic role. It
    never promotes every extracted entity or JCTB data item to owl:Class.
    """
    if not isinstance(semantic_data, dict):
        return _empty_ontology()

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
