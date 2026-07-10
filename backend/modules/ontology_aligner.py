from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.modules.ontology_stats import count_ontology_stats


NOISE_LABELS = {"目录", "前言", "范围", "编号", "中文简称", "数据项名", "解释/举例", "值空间", "引用编号"}


def align_ontology(ontology: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and deduplicate ontology output for OWL generation."""
    if not isinstance(ontology, dict):
        ontology = {}

    classes = _normalize_classes(ontology.get("classes", []))
    class_names = {item["name"] for item in classes}
    class_codes = {item.get("code") for item in classes if item.get("code")}
    properties = _normalize_properties(ontology.get("datatype_properties") or ontology.get("properties", []))
    object_properties = _normalize_object_properties(ontology.get("object_properties", []))
    relations = _normalize_relations(ontology.get("relations", []))
    class_hierarchy = _normalize_hierarchy(ontology.get("class_hierarchy", []))

    for prop in properties:
        domain = prop.get("domain") or "EducationResource"
        if domain not in class_names and domain not in class_codes and f"DataClass{domain}" not in class_names:
            classes.append({"name": domain, "id": domain, "label": domain, "description": "Added from datatype property domain.", "low_confidence": True})
            class_names.add(domain)

    for prop in object_properties:
        for endpoint in (prop.get("domain"), prop.get("range")):
            if endpoint and endpoint not in class_names and endpoint not in class_codes and f"DataClass{endpoint}" not in class_names:
                classes.append({"name": endpoint, "id": endpoint, "label": endpoint, "description": "Added from object property endpoint.", "low_confidence": True})
                class_names.add(endpoint)

    for relation in relations:
        for endpoint in (relation.get("source"), relation.get("target"), relation.get("subject"), relation.get("object")):
            endpoint = _safe_class_name(endpoint)
            if endpoint and endpoint not in class_names and endpoint not in class_codes and f"DataClass{endpoint}" not in class_names:
                classes.append({"name": endpoint, "id": endpoint, "label": endpoint, "description": "Added from relation endpoint.", "low_confidence": True})
                class_names.add(endpoint)

    result = {
        "classes": classes,
        "properties": properties,
        "datatype_properties": properties,
        "object_properties": object_properties,
        "relations": relations,
        "class_hierarchy": class_hierarchy,
    }
    for key in ("metadata", "warnings", "stats", "alignment_mappings", "source_mappings", "alignment_hints"):
        if key in ontology:
            result[key] = ontology[key]
    if "stats" in result:
        result["stats"].update(count_ontology_stats(result))
    return result


def align_multiple_ontologies(ontologies: list, source_docs: Optional[list] = None) -> dict:
    ontologies = [item for item in ontologies if isinstance(item, dict)] if isinstance(ontologies, list) else []
    source_docs = source_docs or []
    aligned = [align_ontology(item) for item in ontologies]
    result = {
        "classes": [],
        "datatype_properties": [],
        "properties": [],
        "object_properties": [],
        "relations": [],
        "class_hierarchy": [],
        "alignment_mappings": [],
        "source_mappings": [],
        "metadata": {
            "source_docs": source_docs,
            "alignment_strategy": "rule_label_id_domain_range_with_blueprint_hints",
        },
    }

    indexes: dict[str, dict[str, dict]] = {
        "classes": {},
        "datatype_properties": {},
        "object_properties": {},
    }
    for ontology_index, ontology in enumerate(aligned):
        source_doc = source_docs[ontology_index] if ontology_index < len(source_docs) else ontology.get("metadata", {}).get("source_docs", [""])[0] if ontology.get("metadata", {}).get("source_docs") else ""
        for key in ("classes", "datatype_properties", "object_properties"):
            for element in ontology.get(key, []) or []:
                if not isinstance(element, dict):
                    continue
                element = dict(element)
                if source_doc and not element.get("source_doc"):
                    element["source_doc"] = source_doc
                target, mapping = _find_alignment(indexes[key], element, key)
                if target:
                    _merge_sources(target, element)
                    result["alignment_mappings"].append(mapping)
                else:
                    result[key].append(element)
                    indexes[key][_element_key(element, key)] = element
                if element.get("source_doc") or element.get("source_record_ids"):
                    result["source_mappings"].append(_source_mapping(element, key))
        result["relations"].extend(ontology.get("relations", []) or [])
        result["class_hierarchy"].extend(ontology.get("class_hierarchy", []) or [])
        for hint in ontology.get("alignment_hints", []) or []:
            if isinstance(hint, dict):
                result["alignment_mappings"].append({
                    "source_element": hint.get("source") or hint.get("source_label"),
                    "target_element": hint.get("target") or hint.get("target_label"),
                    "mapping_type": hint.get("mapping_type") or "blueprint_hint",
                    "confidence": float(hint.get("confidence", 0.75) or 0.75),
                    "evidence": hint.get("evidence", []),
                    "generated_by": "llm_blueprint_hint",
                })

    result["properties"] = result["datatype_properties"]
    result["relations"] = _dedupe_dicts(result["relations"], ("subject", "source", "predicate", "type", "object", "target"))
    result["class_hierarchy"] = _dedupe_dicts(result["class_hierarchy"], ("parent", "child"))
    result["source_mappings"] = _dedupe_dicts(result["source_mappings"], ("element_type", "element_id", "source_doc"))
    result["alignment_mappings"] = _dedupe_dicts(result["alignment_mappings"], ("source_element", "target_element", "mapping_type"))
    result["metadata"]["aligned_ontology_count"] = len(aligned)
    result["stats"] = {
        "aligned_ontology_count": len(aligned),
        "alignment_mappings": len(result["alignment_mappings"]),
        "source_mappings": len(result["source_mappings"]),
        **count_ontology_stats(result),
    }
    return result


def _normalize_classes(items: Any) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in _as_dicts(items):
        label = _text(item.get("label") or item.get("name") or item.get("id"))
        name = _safe_class_name(item.get("id") or item.get("name") or label)
        if not name or _is_noise(label):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cls = {"id": name, "name": name, "code": _text(item.get("code")), "label": label or name, "description": _text(item.get("description"))}
        parent = _safe_class_name(item.get("parent"))
        if parent and parent != name:
            cls["parent"] = parent
        _copy_optional(item, cls)
        result.append(cls)
    return result


def _normalize_properties(items: Any) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in _as_dicts(items):
        label = _text(item.get("label") or item.get("name") or item.get("id"))
        name = _safe_property_name(item.get("id") or item.get("name") or label)
        domain = _safe_class_name(item.get("domain") or "EducationResource") or "EducationResource"
        if not name or _is_noise(label):
            continue
        key = (domain.lower(), name.lower())
        if key in seen:
            continue
        seen.add(key)
        prop = {
            "id": name,
            "name": name,
            "code": _text(item.get("code")),
            "label": label or name,
            "domain": domain,
            "range": _normalize_range(item.get("range") or item.get("data_type"), label, name, item.get("description")),
            "description": _text(item.get("description")),
        }
        _copy_optional(item, prop)
        result.append(prop)
    return result


def _normalize_object_properties(items: Any) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in _as_dicts(items):
        name = _safe_property_name(item.get("id") or item.get("name") or item.get("predicate") or item.get("label"))
        domain = _safe_class_name(item.get("domain") or item.get("source") or item.get("subject"))
        range_ = _safe_class_name(item.get("range") or item.get("target") or item.get("object"))
        if not name or not domain or not range_:
            continue
        key = (domain.lower(), name.lower(), range_.lower())
        if key in seen:
            continue
        seen.add(key)
        prop = {"id": name, "name": name, "label": _text(item.get("label")) or name, "domain": domain, "range": range_, "description": _text(item.get("description") or item.get("reason"))}
        _copy_optional(item, prop)
        result.append(prop)
    return result


def _normalize_relations(items: Any) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in _as_dicts(items):
        source = _safe_class_name(item.get("source") or item.get("subject"))
        target = _safe_class_name(item.get("target") or item.get("object"))
        rel_type = _safe_property_name(item.get("type") or item.get("predicate") or item.get("relation"))
        if not source or not target or not rel_type:
            continue
        key = (source.lower(), target.lower(), rel_type.lower())
        if key in seen:
            continue
        seen.add(key)
        relation = {"source": source, "subject": source, "target": target, "object": target, "type": rel_type, "predicate": rel_type, "label": _text(item.get("label")) or rel_type, "description": _text(item.get("description") or item.get("reason"))}
        _copy_optional(item, relation)
        result.append(relation)
    return result


def _normalize_hierarchy(items: Any) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in _as_dicts(items):
        parent = _safe_class_name(item.get("parent"))
        child = _safe_class_name(item.get("child"))
        if not parent or not child or parent == child:
            continue
        key = (parent.lower(), child.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append({"parent": parent, "child": child, "evidence": item.get("evidence", [])})
    return result


def _copy_optional(source: Dict[str, Any], target: Dict[str, Any]) -> None:
    for key in ("evidence", "reason", "low_confidence", "source_record_ids", "generated_by"):
        if source.get(key):
            target[key] = source[key]
    if not target.get("evidence") and not target.get("reason"):
        target["low_confidence"] = True


def _as_dicts(items: Any) -> List[Dict[str, Any]]:
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_class_name(value: Any) -> str:
    text = _safe_identifier(value)
    if not text:
        return ""
    return "".join(part[:1].upper() + part[1:] for part in text.split("_") if part)


def _safe_property_name(value: Any) -> str:
    text = _text(value)
    match = re.search(r"\b([A-Z]{2,}[A-Z0-9]*\d{4,})\b", text, flags=re.I)
    if match:
        return match.group(1).lower()
    return _safe_identifier(value).lower()[:100]


def _safe_identifier(value: Any) -> str:
    text = _text(value)
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")
    return re.sub(r"_+", "_", text)


def _is_noise(label: str) -> bool:
    text = _text(label)
    if not text or text in NOISE_LABELS:
        return True
    return len(text) == 1


def _normalize_range(value: Any, label: str = "", name: str = "", description: Any = "") -> str:
    text = _text(value).lower()
    if text in {"string", "integer", "decimal", "boolean", "date", "time"}:
        return text
    if text in {"int"}:
        return "integer"
    if text in {"float", "number"}:
        return "decimal"
    if text in {"bool"}:
        return "boolean"
    return infer_simple_range(label, name, _text(description))


def infer_simple_range(label: str, name: str = "", description: str = "") -> str:
    text = f"{label} {name} {description}".lower()
    if any(word in text for word in ("date", "日期", "年月")):
        return "date"
    if any(word in text for word in ("int", "integer", "人数", "数量", "个数")):
        return "integer"
    if any(word in text for word in ("decimal", "float", "number", "金额", "面积")):
        return "decimal"
    if any(word in text for word in ("bool", "boolean", "是否", "标志")):
        return "boolean"
    return "string"


def _find_alignment(index: dict[str, dict], element: dict, element_type: str) -> Tuple[Optional[dict], Optional[dict]]:
    key = _element_key(element, element_type)
    if key in index:
        return index[key], _mapping(element, index[key], "same_id_or_label", 0.98)
    reference_id = str(element.get("reference_id") or element.get("source_code") or "").strip().lower()
    norm = _normalized_label(element)
    for target in index.values():
        target_reference_id = str(target.get("reference_id") or target.get("source_code") or "").strip().lower()
        if reference_id and reference_id == target_reference_id:
            return target, _mapping(element, target, "same_reference_or_code", 0.94)
        target_norm = _normalized_label(target)
        if norm and norm == target_norm:
            return target, _mapping(element, target, "normalized_label", 0.95)
        if element_type != "classes":
            same_shape = (
                _safe_class_name(element.get("domain")) == _safe_class_name(target.get("domain"))
                and _safe_class_name(element.get("range")) == _safe_class_name(target.get("range"))
            )
            if same_shape and _similar(norm, target_norm) >= 0.82:
                return target, _mapping(element, target, "domain_range_label_similarity", 0.86)
        elif _similar(norm, target_norm) >= 0.9:
            return target, _mapping(element, target, "label_similarity", 0.88)
    return None, None


def _element_key(element: dict, element_type: str) -> str:
    if element_type == "classes":
        return _safe_class_name(element.get("id") or element.get("name") or element.get("label")).lower()
    domain = _safe_class_name(element.get("domain") or "")
    range_ = _safe_class_name(element.get("range") or "")
    name = _safe_property_name(element.get("id") or element.get("name") or element.get("label"))
    return "|".join(part.lower() for part in (domain, name, range_) if part)


def _normalized_label(element: dict) -> str:
    text = _text(element.get("label") or element.get("name") or element.get("id"))
    return re.sub(r"[\W_]+", "", text, flags=re.U).lower()


def _similar(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def _mapping(source: dict, target: dict, mapping_type: str, confidence: float) -> dict:
    return {
        "source_element": source.get("id") or source.get("name") or source.get("label"),
        "target_element": target.get("id") or target.get("name") or target.get("label"),
        "mapping_type": mapping_type,
        "confidence": confidence,
        "evidence": [source.get("label") or "", target.get("label") or ""],
        "generated_by": "rule_alignment",
    }


def _merge_sources(target: dict, source: dict) -> None:
    for key in ("source_record_ids", "evidence"):
        merged = []
        for value in [*(_as_list(target.get(key))), *(_as_list(source.get(key)))]:
            if value not in merged:
                merged.append(value)
        if merged:
            target[key] = merged
    for key in ("source_doc", "source_table"):
        if source.get(key) and not target.get(key):
            target[key] = source[key]


def _source_mapping(element: dict, element_type: str) -> dict:
    return {
        "element_type": element_type,
        "element_id": element.get("id") or element.get("name") or element.get("label"),
        "source_doc": element.get("source_doc", ""),
        "source_record_ids": _as_list(element.get("source_record_ids")),
        "evidence": _as_list(element.get("evidence")),
    }


def _dedupe_dicts(items: list, keys: tuple[str, ...]) -> list:
    seen = set()
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        marker = tuple(str(item.get(key) or "").lower() for key in keys if item.get(key))
        if not marker:
            marker = (str(item),)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result



