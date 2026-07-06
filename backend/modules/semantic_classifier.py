"""Semantic classification for ontology construction.

This module separates abstract concepts, data attributes, and object relations
before OWL generation. JCTB/JCTB-like data items are treated as properties by
default, not classes.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple


PROPERTY_TYPE_HINTS = {
    "field",
    "property",
    "attribute",
    "data_item",
    "dataitem",
    "indicator",
    "enum",
}

CLASS_TYPE_HINTS = {
    "class",
    "concept",
    "organization",
    "person",
    "course",
    "document",
    "standard",
}

PROPERTY_LABEL_HINTS = (
    "电话",
    "手机",
    "邮箱",
    "邮件",
    "邮政编码",
    "邮编",
    "编号",
    "代码",
    "名称",
    "姓名",
    "地址",
    "日期",
    "时间",
    "标识",
    "状态",
    "类型",
    "长度",
    "值空间",
)

DOMAIN_KEYWORDS = (
    ("学生", "Student", "学生"),
    ("学校", "School", "学校"),
    ("院校", "School", "学校"),
    ("联系人", "ContactInfo", "联系信息"),
    ("联系", "ContactInfo", "联系信息"),
    ("教师", "Teacher", "教师"),
    ("课程", "Course", "课程"),
    ("班级", "ClassGroup", "班级"),
    ("专业", "Major", "专业"),
    ("机构", "Organization", "机构"),
)

DATA_TYPE_RANGE = {
    "n": "decimal",
    "number": "decimal",
    "integer": "integer",
    "int": "integer",
    "float": "decimal",
    "decimal": "decimal",
    "d": "date",
    "date": "date",
    "datetime": "dateTime",
    "b": "boolean",
    "bool": "boolean",
    "boolean": "boolean",
    "object": "string",
    "string": "string",
}


def semantic_classify(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Classify extracted items into classes, properties, and relations."""
    entity_json = payload.get("entity_json", payload) if isinstance(payload, dict) else {}
    clean_data = payload.get("clean_data", {}) if isinstance(payload, dict) else {}
    records = clean_data.get("records", []) if isinstance(clean_data, dict) else []

    classes: List[Dict[str, str]] = []
    properties: List[Dict[str, str]] = []
    relations: List[Dict[str, str]] = []
    items: List[Dict[str, str]] = []
    class_seen = set()
    property_seen = set()
    relation_seen = set()

    def add_class(name: str, label: str = "", description: str = "") -> None:
        name = _safe_identifier(name or label, pascal=True)
        if not name:
            return
        key = name.lower()
        if key in class_seen:
            return
        class_seen.add(key)
        classes.append({
            "name": name,
            "label": label or name,
            "description": description,
        })
        items.append({"name": name, "label": label or name, "type": "class"})

    def add_property(
        name: str,
        label: str,
        domain: str,
        range_: str = "string",
        description: str = "",
    ) -> None:
        prop_name = _safe_identifier(name or label, pascal=False)
        domain_name = _safe_identifier(domain or "EducationResource", pascal=True)
        if not prop_name:
            return
        key = (domain_name.lower(), prop_name.lower())
        if key in property_seen:
            return
        property_seen.add(key)
        add_class(domain_name, _label_for_domain(domain_name), "Inferred concept domain.")
        properties.append({
            "name": prop_name,
            "label": label or prop_name,
            "domain": domain_name,
            "range": _normalize_range(range_),
            "description": description,
        })
        items.append({"name": prop_name, "label": label or prop_name, "type": "property"})

    def add_relation(relation: Dict[str, Any]) -> None:
        source = _safe_identifier(
            relation.get("source") or relation.get("subject"),
            pascal=True,
        )
        target = _safe_identifier(
            relation.get("target") or relation.get("object"),
            pascal=True,
        )
        rel_type = _safe_identifier(
            relation.get("type") or relation.get("predicate") or relation.get("relation"),
            pascal=False,
        )
        if not source or not target or not rel_type:
            return
        key = (source.lower(), rel_type.lower(), target.lower())
        if key in relation_seen:
            return
        relation_seen.add(key)
        add_class(source, _label_for_domain(source), "Relation source concept.")
        add_class(target, _label_for_domain(target), "Relation target concept.")
        relations.append({
            "source": source,
            "target": target,
            "type": rel_type,
            "label": str(relation.get("label") or rel_type),
            "description": str(relation.get("description") or ""),
        })
        items.append({"name": rel_type, "label": str(relation.get("label") or rel_type), "type": "relation"})

    for record in _as_list(records):
        if not isinstance(record, dict):
            continue
        label = _first_text(record.get("cn_name"), record.get("item_name"), record.get("label"))
        name = _first_text(record.get("id"), record.get("item_name"), label)
        domain = _infer_domain(
            " ".join(
                _first_text(record.get(key))
                for key in ("source_table", "item_name", "cn_name", "description")
            )
        )
        add_property(
            name=name,
            label=label or name,
            domain=domain,
            range_=record.get("data_type", "string"),
            description=_record_description(record),
        )

    for entity in _as_list(entity_json.get("entities", [])):
        if not isinstance(entity, dict):
            continue
        name = _first_text(entity.get("name"), entity.get("label"))
        label = _first_text(entity.get("label"), name)
        item_type = _first_text(entity.get("semantic_type"), entity.get("type")).lower()
        if _is_property_like(name, label, item_type):
            domain = _infer_domain(_first_text(entity.get("description"), entity.get("evidence"), label))
            add_property(
                name=name,
                label=label or name,
                domain=domain,
                range_=entity.get("data_type", "string"),
                description=_first_text(entity.get("description"), entity.get("evidence")),
            )
        else:
            add_class(name, label, _first_text(entity.get("description"), entity.get("evidence")))

    for attribute in _as_list(entity_json.get("attributes", [])):
        if not isinstance(attribute, dict):
            continue
        domain = _first_text(attribute.get("entity"), attribute.get("domain"), "EducationResource")
        add_property(
            name=_first_text(attribute.get("name"), attribute.get("label")),
            label=_first_text(attribute.get("label"), attribute.get("name")),
            domain=domain,
            range_=attribute.get("data_type", attribute.get("range", "string")),
            description=_first_text(attribute.get("description"), attribute.get("evidence")),
        )

    for relation in _as_list(entity_json.get("relations", [])):
        if isinstance(relation, dict):
            add_relation(relation)

    if not classes and properties:
        add_class("EducationResource", "教育资源", "Fallback domain concept.")

    return {
        "classes": classes,
        "properties": properties,
        "relations": relations,
        "items": items,
    }


def classify_entity(entity: Dict[str, Any]) -> Dict[str, str]:
    """Classify a single extracted item."""
    name = _first_text(entity.get("name"), entity.get("label"))
    label = _first_text(entity.get("label"), name)
    item_type = _first_text(entity.get("semantic_type"), entity.get("type")).lower()
    semantic_type = "property" if _is_property_like(name, label, item_type) else "class"
    return {"name": name, "label": label, "type": semantic_type}


def _is_property_like(name: str, label: str, item_type: str) -> bool:
    if item_type in PROPERTY_TYPE_HINTS:
        return True
    if item_type in CLASS_TYPE_HINTS:
        return False
    if re.match(r"^JCTB[A-Z0-9]*\d{4,}$", str(name or ""), flags=re.IGNORECASE):
        return True
    return any(hint in str(label or "") for hint in PROPERTY_LABEL_HINTS)


def _infer_domain(text: str) -> str:
    for keyword, domain, _label in DOMAIN_KEYWORDS:
        if keyword in text:
            return domain
    return "EducationResource"


def _label_for_domain(name: str) -> str:
    for _keyword, domain, label in DOMAIN_KEYWORDS:
        if domain.lower() == str(name).lower():
            return label
    if str(name) == "EducationResource":
        return "教育资源"
    return name


def _normalize_range(value: Any) -> str:
    text = str(value or "string").strip().lower()
    return DATA_TYPE_RANGE.get(text, "string")


def _safe_identifier(value: Any, pascal: bool) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text, flags=re.UNICODE).strip("_")
    if not text:
        return ""
    if re.search(r"[\u4e00-\u9fff]", text):
        return text
    parts = [part for part in text.split("_") if part]
    if pascal:
        return "".join(part[:1].upper() + part[1:] for part in parts)
    return "_".join(part.lower() for part in parts)


def _record_description(record: Dict[str, Any]) -> str:
    parts = [
        _first_text(record.get("item_name")),
        _first_text(record.get("description")),
        _first_text(record.get("value_space")),
        _first_text(record.get("reference")),
    ]
    return "；".join(part for part in parts if part)


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _as_list(value: Any) -> Iterable[Any]:
    return value if isinstance(value, list) else []
