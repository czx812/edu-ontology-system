from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return _text(value).lower()


def _file_name(ontology: dict) -> str:
    metadata = ontology.get("metadata", {}) if isinstance(ontology, dict) else {}
    docs = metadata.get("source_docs") if isinstance(metadata.get("source_docs"), list) else []
    first = docs[0] if docs else metadata.get("source_file") or ""
    return Path(str(first)).name if first else ""


def _class_id(item: dict) -> str:
    return _text(item.get("id") or item.get("name") or item.get("label"))


def _is_code_like(value: str) -> bool:
    text = _text(value)
    return bool(text and any(ch.isdigit() for ch in text) and len(text) >= 8 and text.upper() == text)


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def cross_file_ontology_align(local_ontologies: list[dict]) -> dict:
    class_mappings: list[dict] = []
    property_mappings: list[dict] = []
    relation_mappings: list[dict] = []
    warnings: list[str] = []

    ontologies = [item for item in local_ontologies if isinstance(item, dict)]
    for left_index in range(len(ontologies)):
        for right_index in range(left_index + 1, len(ontologies)):
            left = ontologies[left_index]
            right = ontologies[right_index]
            left_file = _file_name(left)
            right_file = _file_name(right)
            class_mappings.extend(_align_classes(left.get("classes", []) or [], right.get("classes", []) or [], left_file, right_file))
            property_mappings.extend(_align_properties(_props(left), _props(right), left_file, right_file))
            relation_mappings.extend(_align_relations(left.get("relations", []) or [], right.get("relations", []) or [], left_file, right_file, property_mappings))

    return {
        "class_mappings": class_mappings,
        "property_mappings": property_mappings,
        "relation_mappings": relation_mappings,
        "warnings": warnings,
    }


def _props(ontology: dict) -> list[dict]:
    items = ontology.get("datatype_properties") or ontology.get("properties") or []
    return [item for item in items if isinstance(item, dict)]


def _align_classes(left: list, right: list, left_file: str, right_file: str) -> list[dict]:
    mappings = []
    for a in [item for item in left if isinstance(item, dict)]:
        a_id = _class_id(a)
        if not a_id or _is_code_like(a_id):
            continue
        for b in [item for item in right if isinstance(item, dict)]:
            b_id = _class_id(b)
            if not b_id or _is_code_like(b_id):
                continue
            a_label = _text(a.get("label") or a_id)
            b_label = _text(b.get("label") or b_id)
            if _norm(a_id) == _norm(b_id):
                mappings.append(_mapping(left_file, right_file, a_id, b_id, "same_as", 1.0, "same class name"))
            elif _norm(a_label) == _norm(b_label):
                mappings.append(_mapping(left_file, right_file, a_id, b_id, "same_as", 1.0, "same class label"))
            elif _similar(a_label, b_label) >= 0.86:
                mappings.append(_mapping(left_file, right_file, a_id, b_id, "possible_same_as", round(_similar(a_label, b_label), 2), "similar class label"))
    return _dedupe(mappings)


def _align_properties(left: list[dict], right: list[dict], left_file: str, right_file: str) -> list[dict]:
    mappings = []
    for a in left:
        for b in right:
            a_code = _text(a.get("code") or a.get("source_code") or a.get("id"))
            b_code = _text(b.get("code") or b.get("source_code") or b.get("id"))
            a_label = _text(a.get("label") or a.get("name"))
            b_label = _text(b.get("label") or b.get("name"))
            a_field = _text(a.get("field_name") or a.get("name"))
            b_field = _text(b.get("field_name") or b.get("name"))
            relation = ""
            confidence = 0.0
            reason = ""
            if a_code and b_code and _norm(a_code) == _norm(b_code):
                relation, confidence, reason = "same_as", 1.0, "same code"
            elif a_field and b_field and _norm(a_field) == _norm(b_field) and _norm(a_label) == _norm(b_label):
                relation, confidence, reason = "same_as", 0.96, "same field and label"
            elif a_label and _norm(a_label) == _norm(b_label) and _similar(_text(a.get("domain")), _text(b.get("domain"))) >= 0.75:
                relation, confidence, reason = "same_as", 0.92, "same label and close domain"
            elif _similar(a_label, b_label) >= 0.88:
                relation, confidence, reason = "possible_same_as", round(_similar(a_label, b_label), 2), "similar label"
            if relation:
                mappings.append({
                    "source_file": left_file,
                    "target_file": right_file,
                    "source_code": a_code,
                    "target_code": b_code,
                    "source": a.get("id") or a.get("name"),
                    "target": b.get("id") or b.get("name"),
                    "relation": relation,
                    "confidence": confidence,
                    "reason": reason,
                })
    return _dedupe(mappings)


def _align_relations(left: list, right: list, left_file: str, right_file: str, property_mappings: list[dict]) -> list[dict]:
    aligned_pairs = {(_norm(m.get("source_code") or m.get("source")), _norm(m.get("target_code") or m.get("target"))) for m in property_mappings if m.get("relation") == "same_as"}
    mappings = []
    for a in [item for item in left if isinstance(item, dict)]:
        a_key = (_norm(a.get("source") or a.get("subject")), _norm(a.get("type") or a.get("predicate")), _norm(a.get("target") or a.get("object")))
        for b in [item for item in right if isinstance(item, dict)]:
            b_key = (_norm(b.get("source") or b.get("subject")), _norm(b.get("type") or b.get("predicate")), _norm(b.get("target") or b.get("object")))
            if a_key == b_key and all(a_key):
                mappings.append(_mapping(left_file, right_file, "|".join(a_key), "|".join(b_key), "same_as", 1.0, "same relation triple"))
            elif (a_key[0], b_key[0]) in aligned_pairs and (a_key[2], b_key[2]) in aligned_pairs and a_key[1] == b_key[1]:
                mappings.append(_mapping(left_file, right_file, "|".join(a_key), "|".join(b_key), "same_as", 0.9, "aligned endpoints"))
    return _dedupe(mappings)


def _mapping(source_file: str, target_file: str, source: str, target: str, relation: str, confidence: float, reason: str) -> dict:
    return {"source_file": source_file, "target_file": target_file, "source": source, "target": target, "relation": relation, "confidence": confidence, "reason": reason}


def _dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        key = tuple(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
