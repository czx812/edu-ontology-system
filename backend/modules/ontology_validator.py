from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Set


def build_rule_draft_properties(records: list, classes: Optional[list] = None, source_doc: str = "") -> List[dict]:
    class_ids = {_class_id(item) for item in classes or [] if isinstance(item, dict) and _class_id(item)} or {"EducationDataElement", "EducationResource"}
    default_domain = _best_default_domain(class_ids)
    properties: List[dict] = []
    used_ids: Set[str] = set()
    for index, record in enumerate(records if isinstance(records, list) else []):
        if not isinstance(record, dict):
            record = {"value": str(record)}
        rid = _record_id(record, index)
        label = _record_label(record, rid)
        prop_id = _unique_id(_property_id_from_record(record, label, rid), used_ids)
        used_ids.add(prop_id)
        domain = _rule_domain(record, class_ids, default_domain)
        source = record.get("source") if isinstance(record.get("source"), dict) else {}
        properties.append({
            "id": prop_id,
            "name": prop_id,
            "label": label or prop_id,
            "domain": domain,
            "range": _range_from_record(record),
            "description": str(record.get("description") or record.get("comment") or "")[:500],
            "source_record_ids": [rid],
            "source_doc": source_doc,
            "source": source,
            "sources": [source] if source else [],
            "source_file": source.get("file_path") or source_doc,
            "source_filename": source.get("filename") or "",
            "source_table": str(record.get("source_table") or record.get("source_section") or source.get("table_index") or ""),
            "evidence": [_evidence(record, rid, label)],
            "generated_by": "rule_draft",
            "confidence": 0.78,
            "source_code": str(record.get("code") or record.get("id") or ""),
            "reference_id": str(record.get("reference") or record.get("reference_id") or ""),
        })
    return properties


def expand_datatype_properties_by_llm_rules(records: list, llm_blueprint: dict, document_structure: Optional[dict] = None, source_doc: str = "") -> List[dict]:
    classes = _normalize_classes(llm_blueprint.get("classes", []))
    class_ids = {_class_id(item) for item in classes if _class_id(item)} or {"EducationResource"}
    default_domain = _best_default_domain(class_ids)
    domain_rules = llm_blueprint.get("domain_inference_rules", []) if isinstance(llm_blueprint, dict) else []
    range_rules = llm_blueprint.get("range_inference_rules", []) if isinstance(llm_blueprint, dict) else []
    mapping_rules = llm_blueprint.get("datatype_property_mapping_rules", []) if isinstance(llm_blueprint, dict) else []
    has_blueprint = bool(llm_blueprint.get("classes") or domain_rules or range_rules or mapping_rules) if isinstance(llm_blueprint, dict) else False

    properties: List[dict] = []
    used_ids: Set[str] = set()
    for index, record in enumerate(records if isinstance(records, list) else []):
        if not isinstance(record, dict):
            record = {"value": str(record)}
        rid = _record_id(record, index)
        label = _record_label(record, rid)
        code = str(record.get("code") or record.get("id") or "").strip()
        prop_id = _unique_id(_property_id_from_record(record, label, rid), used_ids)
        used_ids.add(prop_id)
        domain, domain_conf = _infer_domain(record, class_ids, domain_rules, mapping_rules, default_domain)
        range_, range_conf = _infer_range(record, range_rules)
        low_confidence = domain_conf < 0.7 or range_conf < 0.7
        source = record.get("source") if isinstance(record.get("source"), dict) else {}
        properties.append({
            "id": prop_id,
            "name": prop_id,
            "label": label or prop_id,
            "domain": domain,
            "range": range_,
            "description": str(record.get("description") or record.get("comment") or "")[:500],
            "source_record_ids": [rid],
            "source_doc": source_doc,
            "source": source,
            "sources": [source] if source else [],
            "source_file": source.get("file_path") or source_doc,
            "source_filename": source.get("filename") or "",
            "source_table": str(record.get("source_table") or record.get("source_section") or source.get("table_index") or ""),
            "evidence": [_evidence(record, rid, label)],
            "generated_by": "llm_rule_expansion" if has_blueprint else "rule_completion",
            "confidence": round(min(domain_conf, range_conf), 2),
            "low_confidence": low_confidence,
            "source_code": code,
        })
    return properties


def validate_and_complete_ontology(ontology: dict, records: list, document_structure: Optional[dict] = None, source_doc: str = "") -> dict:
    ontology = _normalize_shape(ontology)
    warnings = list(ontology.get("warnings", []) or [])
    classes = ontology["classes"]
    datatype_properties = ontology["datatype_properties"]
    object_properties = ontology["object_properties"]
    relations = ontology["relations"]
    hierarchy = ontology["class_hierarchy"]

    if not classes:
        classes.append({
            "id": "EducationResource",
            "name": "EducationResource",
            "label": "Education Resource",
            "description": "Generic class added because LLM blueprint returned no classes.",
            "generated_by": "rule_completion",
            "low_confidence": True,
        })
        warnings.append("classes was empty; added EducationResource.")

    classes[:] = _dedupe_classes(classes)
    class_ids = {_class_id(item) for item in classes if _class_id(item)}
    if not class_ids:
        class_ids.add("EducationResource")
        classes.append({"id": "EducationResource", "name": "EducationResource", "label": "Education Resource", "generated_by": "rule_completion"})

    existing_ids = {_record_source_key(prop) for prop in datatype_properties if isinstance(prop, dict)}
    if records and len(existing_ids) < len(records):
        expanded = expand_datatype_properties_by_llm_rules(records, ontology, document_structure or {}, source_doc=source_doc)
        by_record = {_record_source_key(prop): prop for prop in expanded if _record_source_key(prop)}
        merged = list(datatype_properties)
        for key, prop in by_record.items():
            if key not in existing_ids:
                merged.append(prop)
        datatype_properties[:] = merged

    datatype_properties[:] = _normalize_datatype_properties(datatype_properties, class_ids, source_doc)
    object_properties[:] = _normalize_object_properties(object_properties, class_ids, warnings)
    relations[:] = _normalize_relations(relations, class_ids, warnings)
    hierarchy[:] = _normalize_hierarchy(hierarchy, class_ids, warnings)

    rule_completed = sum(1 for prop in datatype_properties if prop.get("generated_by") == "rule_completion")
    llm_rule_expanded = sum(1 for prop in datatype_properties if prop.get("generated_by") == "llm_rule_expansion")
    source_mapped = sum(1 for item in [*classes, *datatype_properties, *object_properties, *relations] if item.get("source_record_ids") or item.get("source_doc"))

    if not datatype_properties:
        warnings.append("datatype_properties is empty after validation.")
    if not object_properties:
        warnings.append("object_properties is empty; export will still include classes and datatype properties.")

    ontology["classes"] = classes
    ontology["datatype_properties"] = datatype_properties
    ontology["properties"] = datatype_properties
    ontology["object_properties"] = object_properties
    ontology["relations"] = relations
    ontology["class_hierarchy"] = hierarchy
    ontology["source_mappings"] = _source_mappings(ontology)
    ontology["warnings"] = _dedupe_text(warnings)
    ontology["validation"] = {
        "rule_completed_properties": rule_completed,
        "datatype_properties_by_llm_rules": llm_rule_expanded,
        "invalid_relations_removed": 0,
        "source_mapped_elements": len(ontology["source_mappings"]) or source_mapped,
        "rule_draft_properties": sum(1 for prop in datatype_properties if prop.get("generated_by") == "rule_draft"),
    }
    return ontology


def _normalize_shape(ontology: dict) -> dict:
    ontology = ontology if isinstance(ontology, dict) else {}
    datatype = ontology.get("datatype_properties") or ontology.get("properties") or []
    return {
        **ontology,
        "classes": ontology.get("classes", []) if isinstance(ontology.get("classes", []), list) else [],
        "datatype_properties": datatype if isinstance(datatype, list) else [],
        "properties": datatype if isinstance(datatype, list) else [],
        "object_properties": ontology.get("object_properties", []) if isinstance(ontology.get("object_properties", []), list) else [],
        "relations": ontology.get("relations", []) if isinstance(ontology.get("relations", []), list) else [],
        "class_hierarchy": ontology.get("class_hierarchy", []) if isinstance(ontology.get("class_hierarchy", []), list) else [],
    }


def _normalize_classes(items: list) -> List[dict]:
    return [_normalize_class(item) for item in items if isinstance(item, dict)]


def _normalize_class(item: dict) -> dict:
    cid = _safe_class_id(item.get("id") or item.get("name") or item.get("label"))
    label = str(item.get("label") or item.get("name") or cid)
    return {**item, "id": cid, "name": cid, "label": label}


def _dedupe_classes(items: List[dict]) -> List[dict]:
    seen = set()
    result = []
    for item in items:
        normalized = _normalize_class(item)
        cid = normalized.get("id")
        if not cid or cid.lower() in seen:
            continue
        seen.add(cid.lower())
        result.append(normalized)
    return result


def _normalize_datatype_properties(items: List[Any], class_ids: Set[str], source_doc: str) -> List[dict]:
    used = set()
    result = []
    fallback_domain = _best_default_domain(class_ids)
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("name") or item.get("id") or "").strip()
        pid = _safe_property_id(item.get("id") or item.get("name") or label)
        if not pid or pid == "property":
            pid = _unique_id("property_" + _short_hash(label or item), used)
        pid = _unique_id(pid, used)
        used.add(pid)
        domain = _safe_class_id(item.get("domain") or fallback_domain)
        if domain not in class_ids:
            domain = fallback_domain
            item["low_confidence"] = True
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        sources = item.get("sources") if isinstance(item.get("sources"), list) else ([source] if source else [])
        prop = {
            **item,
            "id": pid,
            "name": pid,
            "label": label or pid,
            "domain": domain,
            "range": _normalize_range(item.get("range") or item.get("data_type"), label, str(item.get("description") or "")),
            "source_record_ids": _as_list(item.get("source_record_ids")),
            "source_doc": item.get("source_doc") or source_doc,
            "source": source,
            "sources": sources,
            "source_file": item.get("source_file") or source.get("file_path") or item.get("source_doc") or source_doc,
            "source_filename": item.get("source_filename") or source.get("filename") or "",
            "source_table": item.get("source_table") or source.get("table_index") or "",
            "evidence": _as_list(item.get("evidence")) or [label or pid],
            "generated_by": item.get("generated_by") or "rule_completion",
            "confidence": float(item.get("confidence", 0.65) or 0.65),
        }
        result.append(prop)
    return result


def _normalize_object_properties(items: List[Any], class_ids: Set[str], warnings: List[str]) -> List[dict]:
    seen = set()
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        domain = _safe_class_id(item.get("domain") or item.get("source") or item.get("subject"))
        range_ = _safe_class_id(item.get("range") or item.get("target") or item.get("object"))
        if domain not in class_ids or range_ not in class_ids:
            warnings.append(f"Removed object property with unknown domain/range: {item.get('id') or item.get('label')}")
            continue
        pid = _safe_property_id(item.get("id") or item.get("name") or item.get("predicate") or item.get("label"))
        marker = (domain.lower(), pid.lower(), range_.lower())
        if not pid or marker in seen:
            continue
        seen.add(marker)
        result.append({**item, "id": pid, "name": pid, "domain": domain, "range": range_, "label": str(item.get("label") or pid)})
    return result


def _normalize_relations(items: List[Any], class_ids: Set[str], warnings: List[str]) -> List[dict]:
    seen = set()
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        subject = _safe_class_id(item.get("subject") or item.get("source"))
        obj = _safe_class_id(item.get("object") or item.get("target"))
        predicate = _safe_property_id(item.get("predicate") or item.get("type") or item.get("relation"))
        if subject not in class_ids or obj not in class_ids or not predicate:
            warnings.append(f"Removed relation with unknown endpoint: {predicate or item}")
            continue
        marker = (subject.lower(), predicate.lower(), obj.lower())
        if marker in seen:
            continue
        seen.add(marker)
        result.append({**item, "subject": subject, "source": subject, "predicate": predicate, "type": predicate, "object": obj, "target": obj})
    return result


def _normalize_hierarchy(items: List[Any], class_ids: Set[str], warnings: List[str]) -> List[dict]:
    seen = set()
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        parent = _safe_class_id(item.get("parent"))
        child = _safe_class_id(item.get("child"))
        if parent not in class_ids or child not in class_ids or parent == child:
            warnings.append(f"Removed class hierarchy with unknown parent/child: {parent}->{child}")
            continue
        marker = (parent.lower(), child.lower())
        if marker in seen:
            continue
        seen.add(marker)
        result.append({**item, "parent": parent, "child": child, "evidence": _as_list(item.get("evidence"))})
    return result


def _infer_domain(record: dict, class_ids: Set[str], domain_rules: list, mapping_rules: list, default_domain: str) -> tuple[str, float]:
    candidates = [str(item) for item in record.get("candidate_domains", []) if str(item)] if isinstance(record.get("candidate_domains"), list) else []
    for candidate in candidates:
        cid = _safe_class_id(candidate)
        if cid in class_ids:
            return cid, 0.86
    blob = _record_blob(record)
    for rule in [*domain_rules, *mapping_rules]:
        if not isinstance(rule, dict):
            continue
        target = _safe_class_id(rule.get("domain") or rule.get("class") or rule.get("target_class"))
        if target not in class_ids:
            continue
        pattern = str(rule.get("pattern") or rule.get("field_pattern") or rule.get("when") or rule.get("match") or "").strip()
        if pattern and pattern.lower() in blob.lower():
            return target, 0.82
    return default_domain, 0.55


def _rule_domain(record: dict, class_ids: Set[str], default_domain: str) -> str:
    candidates = [str(item) for item in record.get("candidate_domains", []) if str(item)] if isinstance(record.get("candidate_domains"), list) else []
    for candidate in candidates:
        cid = _safe_class_id(candidate)
        if cid in class_ids:
            return cid
    if "EducationDataElement" in class_ids:
        return "EducationDataElement"
    return default_domain


def _infer_range(record: dict, range_rules: list) -> tuple[str, float]:
    blob = _record_blob(record)
    for rule in range_rules:
        if not isinstance(rule, dict):
            continue
        pattern = str(rule.get("pattern") or rule.get("field_pattern") or rule.get("when") or rule.get("match") or "").strip()
        value = _normalize_range(rule.get("range") or rule.get("datatype") or rule.get("target_range"), "", "")
        if pattern and pattern.lower() in blob.lower():
            return value, 0.82
    return _range_from_record(record), 0.65


def _record_id(record: Any, index: int) -> str:
    if isinstance(record, dict):
        return str(record.get("id") or record.get("code") or record.get("record_id") or record.get("name") or f"record_{index + 1}")
    return f"record_{index + 1}"


def _record_label(record: Any, fallback: str) -> str:
    if isinstance(record, dict):
        return str(record.get("cn_name") or record.get("item_name") or record.get("label") or record.get("name") or fallback)
    return fallback


def _property_id_from_record(record: dict, label: str, rid: str) -> str:
    code = str(record.get("code") or record.get("id") or "").strip()
    if code:
        return _safe_property_id(code)
    base = str(record.get("item_name") or record.get("name") or record.get("short_name") or label or "field")
    safe = _safe_property_id(base)
    if safe == "property":
        safe = "field"
    return safe + "_" + _short_hash(record)


def _range_from_record(record: Any) -> str:
    text = ""
    if isinstance(record, dict):
        text = _record_blob(record).lower()
    if any(word in text for word in ("date", "日期", "年月")):
        return "date"
    if any(word in text for word in ("int", "integer", "人数", "数量", "个数", "长度")):
        return "integer"
    if any(word in text for word in ("decimal", "float", "number", "金额", "面积")):
        return "decimal"
    if any(word in text for word in ("bool", "boolean", "是否", "标志")):
        return "boolean"
    return "string"


def _normalize_range(value: Any, label: str, description: str) -> str:
    text = str(value or "").strip().lower()
    mapping = {"int": "integer", "float": "decimal", "number": "decimal", "bool": "boolean", "datetime": "date"}
    text = mapping.get(text, text)
    if text in {"string", "integer", "decimal", "boolean", "date", "time"}:
        return text
    return _range_from_record({"cn_name": label, "description": description})


def _class_id(item: dict) -> str:
    return _safe_class_id(item.get("id") or item.get("name") or item.get("label"))


def _safe_class_id(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    if not text:
        return ""
    return "".join(part[:1].upper() + part[1:] for part in text.split("_") if part)


def _safe_property_id(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"\b([A-Z]{2,}[A-Z0-9]*\d{4,})\b", text, flags=re.I)
    if match:
        return match.group(1).lower()
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_").lower()
    text = re.sub(r"_+", "_", text)
    return text[:100] or "property"


def _unique_id(base: str, used: Set[str]) -> str:
    base = _safe_property_id(base)
    if base not in used and base != "property":
        return base
    suffix = 2
    while f"{base}_{suffix}" in used:
        suffix += 1
    return f"{base}_{suffix}"


def _best_default_domain(class_ids: Set[str]) -> str:
    for preferred in ("EducationResource", "EducationDataElement", "DataElement"):
        if preferred in class_ids:
            return preferred
    return sorted(class_ids)[0] if class_ids else "EducationResource"


def _record_blob(record: dict) -> str:
    return " ".join(str(record.get(key) or "") for key in ("id", "code", "item_name", "cn_name", "data_type", "description", "source_table", "source_section", "reference"))


def _evidence(record: dict, rid: str, label: str) -> str:
    bits = [rid, label, str(record.get("data_type") or ""), str(record.get("description") or "")[:120]]
    return " | ".join(bit for bit in bits if bit)


def _record_source_key(prop: dict) -> str:
    ids = _as_list(prop.get("source_record_ids"))
    return str(ids[0]) if ids else ""


def _source_mappings(ontology: dict) -> List[dict]:
    mappings = []
    for element_type in ("classes", "datatype_properties", "object_properties", "relations"):
        items = ontology.get(element_type, []) if isinstance(ontology, dict) else []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("source_doc") or item.get("source_record_ids") or item.get("evidence"):
                mappings.append({
                    "element_type": element_type,
                    "element_id": item.get("id") or item.get("name") or item.get("label"),
                    "source_doc": item.get("source_doc", ""),
                    "source_record_ids": _as_list(item.get("source_record_ids")),
                    "source_table": item.get("source_table", ""),
                    "evidence": _as_list(item.get("evidence")),
                })
    return mappings


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _short_hash(value: Any) -> str:
    return hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:8]


def _dedupe_text(items: List[Any]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


