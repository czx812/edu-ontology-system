from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


NOISE_LABELS = {
    "目录",
    "前言",
    "范围",
    "规范性引用文件",
    "术语和定义",
    "编号",
    "中文简称",
    "数据项名",
    "解释/举例",
    "值空间",
    "引用编号",
    "码",
    "号",
    "称",
    "位",
    "期",
    "箱",
    "女",
    "话",
}


def align_ontology(ontology: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and deduplicate B-layer ontology output for OWL generation."""
    if not isinstance(ontology, dict):
        ontology = {}

    classes = _normalize_classes(ontology.get("classes", []))
    class_names = {item["name"] for item in classes}
    properties = _normalize_properties(ontology.get("properties", []))
    relations = _normalize_relations(ontology.get("relations", []))

    for prop in properties:
        domain = prop.get("domain") or "EducationResource"
        if domain not in class_names:
            classes.append({
                "name": domain,
                "label": domain,
                "description": "由属性 domain 引用补充的类。",
                "low_confidence": True,
            })
            class_names.add(domain)

    for relation in relations:
        for endpoint in (relation.get("source"), relation.get("target")):
            if endpoint and endpoint not in class_names:
                classes.append({
                    "name": endpoint,
                    "label": endpoint,
                    "description": "由关系端点引用补充的类。",
                    "low_confidence": True,
                })
                class_names.add(endpoint)

    result = {
        "classes": classes,
        "properties": properties,
        "relations": relations,
    }
    for key in ("metadata", "warnings", "stats"):
        if key in ontology:
            result[key] = ontology[key]
    return result


def _normalize_classes(items: Any) -> List[Dict[str, Any]]:
    seen = set()
    result: List[Dict[str, Any]] = []
    for item in _as_dicts(items):
        label = _text(item.get("label") or item.get("name"))
        name = _safe_class_name(item.get("name") or label)
        if not name or _is_noise(label):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cls = {
            "name": name,
            "label": label or name,
            "description": _text(item.get("description")),
        }
        parent = _safe_class_name(item.get("parent"))
        if parent and parent != name:
            cls["parent"] = parent
        _copy_optional(item, cls)
        result.append(cls)
    return result


def _normalize_properties(items: Any) -> List[Dict[str, Any]]:
    seen = set()
    name_counts: Dict[Tuple[str, str], int] = {}
    result: List[Dict[str, Any]] = []
    for item in _as_dicts(items):
        label = _text(item.get("label") or item.get("name"))
        name = _safe_property_name(item.get("name") or label)
        domain = _safe_class_name(item.get("domain") or "EducationResource") or "EducationResource"
        if not name or _is_noise(label):
            continue
        key = (domain.lower(), name.lower())
        if key in seen:
            suffix = _safe_property_name(label)
            if suffix and suffix != name:
                name = f"{name}_{suffix[:24]}"
                key = (domain.lower(), name.lower())
            else:
                base_key = (domain.lower(), name.lower())
                name_counts[base_key] = name_counts.get(base_key, 1) + 1
                name = f"{name}_{name_counts[base_key]}"
                key = (domain.lower(), name.lower())
        if key in seen:
            continue
        seen.add(key)
        prop = {
            "name": name,
            "label": label or name,
            "domain": domain,
            "range": _normalize_range(item.get("range") or item.get("data_type"), label, name, item.get("description")),
            "description": _text(item.get("description")),
        }
        _copy_optional(item, prop)
        result.append(prop)
    return result


def _normalize_relations(items: Any) -> List[Dict[str, Any]]:
    seen = set()
    result: List[Dict[str, Any]] = []
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
        relation = {
            "source": source,
            "target": target,
            "type": rel_type,
            "label": _text(item.get("label")) or rel_type,
            "description": _text(item.get("description") or item.get("reason")),
        }
        _copy_optional(item, relation)
        result.append(relation)
    return result


def _copy_optional(source: Dict[str, Any], target: Dict[str, Any]) -> None:
    for key in ("evidence", "reason", "low_confidence"):
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
    if len(text) == 1:
        return True
    if any(word in text for word in ("中华人民共和国教育行业标准", "教育部发布", "--- Table")):
        return True
    return False


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
    text = f"{label} {name} {description}"
    if any(word in text for word in ("日期", "日", "出生日期", "入学年月", "建校年月", "出版日期", "评定日期")):
        return "date"
    if "时间" in text:
        return "time"
    if any(word in text for word in ("人数", "人口", "数量", "层数", "页数", "个数", "时数")):
        return "integer"
    if any(word in text for word in ("金额", "收入", "支出", "费用", "价格", "工资", "拨款", "债务", "经费", "面积", "单价")):
        return "decimal"
    if any(word in text for word in ("是否", "标志", "正常", "不正常")):
        return "boolean"
    return "string"
