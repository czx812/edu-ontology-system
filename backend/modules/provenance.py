from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from config import settings


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return _text(value).lower()


def _first(record: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(record.get(key))
        if value:
            return value
    return ""


def _record_id(record: Dict[str, Any]) -> str:
    return _first(record, "id", "code")


def _record_item_name(record: Dict[str, Any]) -> str:
    return _first(record, "item_name", "field_name")


def _record_cn_name(record: Dict[str, Any]) -> str:
    return _first(record, "cn_name", "name")


def _record_value_space(record: Dict[str, Any]) -> str:
    return _first(record, "value_space", "value_range")


def _record_source_table(record: Dict[str, Any]) -> str:
    source_table = _text(record.get("source_table"))
    if source_table:
        return source_table

    source = record.get("source", {})
    if isinstance(source, dict):
        page = source.get("page")
        table_index = source.get("table_index")
        if page is not None or table_index is not None:
            return f"page_{page}_table_{table_index}"

    return ""


def _record_source_row_index(record: Dict[str, Any]) -> Any:
    if "source_row_index" in record:
        return record.get("source_row_index")

    source = record.get("source", {})
    if isinstance(source, dict):
        return source.get("row_index", "")

    return ""


def _record_text(record: Dict[str, Any]) -> str:
    fields = [
        _record_id(record),
        _record_item_name(record),
        _record_cn_name(record),
        _text(record.get("description")),
        _record_value_space(record),
        _record_source_table(record),
    ]
    return " ".join(x for x in fields if x).lower()


def _keywords(name: str, label: str) -> List[str]:
    result = []

    for value in (name, label):
        value = _text(value)
        if value and value not in result:
            result.append(value)

    return result


def _match_record(name: str, label: str, record: Dict[str, Any]) -> bool:
    record_id = _norm(_record_id(record))
    item_name = _norm(_record_item_name(record))
    cn_name = _norm(_record_cn_name(record))
    all_text = _record_text(record)

    for word in _keywords(name, label):
        key = _norm(word)

        if not key:
            continue

        # 最可靠：完全相等，例如 ontology_name = XXDM，record.item_name = XXDM
        if key in {record_id, item_name, cn_name}:
            return True

        # 兼容：中文标签出现在记录内容中，例如 学校代码
        if key in all_text:
            return True

        # 兼容：LLM 生成名称比原字段长
        if cn_name and cn_name in key:
            return True

        if item_name and item_name in key:
            return True

    return False


def _source_key(source: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return (
        str(source.get("source_file", "")),
        str(source.get("source_table", "")),
        str(source.get("source_row_index", "")),
        str(source.get("id", "")),
    )


def _find_sources(
    name: str,
    label: str,
    records: List[Dict[str, Any]],
    source_file: str,
) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str, str]] = set()

    for record in records:
        if not isinstance(record, dict):
            continue

        if not _match_record(name, label, record):
            continue

        source = {
            "source_file": _text(record.get("source_file") or source_file),
            "source_table": _record_source_table(record),
            "source_row_index": _record_source_row_index(record),

            "id": _record_id(record),
            "item_name": _record_item_name(record),
            "cn_name": _record_cn_name(record),
            "data_type": _text(record.get("data_type")),
            "length": _text(record.get("length")),
            "constraint": _text(record.get("constraint")),
            "value_space": _record_value_space(record),
            "description": _text(record.get("description")),
            "reference": _text(record.get("reference")),
        }

        key = _source_key(source)

        if key not in seen:
            seen.add(key)
            sources.append(source)

    return sources


def _class_name_and_label(item: Any) -> Tuple[str, str]:
    if isinstance(item, dict):
        name = _text(item.get("name") or item.get("id") or item.get("label"))
        label = _text(item.get("label") or item.get("cn_name") or name)
    else:
        name = _text(item)
        label = name

    return name, label


def _property_name_and_label(item: Any) -> Tuple[str, str]:
    if isinstance(item, dict):
        name = _text(
            item.get("name")
            or item.get("id")
            or item.get("item_name")
            or item.get("field_name")
        )
        label = _text(
            item.get("label")
            or item.get("cn_name")
            or item.get("name")
            or name
        )
    else:
        name = _text(item)
        label = name

    return name, label


def _save_trace_map(trace_map: Dict[str, Any]) -> str:
    settings.TRACE_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_path = settings.TRACE_DIR / f"trace_{timestamp}.json"

    trace_path.write_text(
        json.dumps(trace_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(trace_path)


def build_trace_map(clean_data: Dict[str, Any], ontology: Dict[str, Any]) -> Dict[str, Any]:
    """
    数据溯源模块：
    用 ontology 中的类、属性、关系，反查 clean_data.records 中的来源记录。
    """

    if not isinstance(clean_data, dict):
        clean_data = {}

    if not isinstance(ontology, dict):
        ontology = {}

    records = clean_data.get("records", [])
    if not isinstance(records, list):
        records = []

    source_file = _text(clean_data.get("source_file"))

    trace_items: List[Dict[str, Any]] = []

    # 1. 类溯源
    for cls in ontology.get("classes", []):
        name, label = _class_name_and_label(cls)
        sources = _find_sources(name, label, records, source_file)

        trace_items.append({
            "ontology_type": "class",
            "ontology_name": name,
            "ontology_label": label,
            "sources": sources,
        })

    # 2. 属性溯源
    for prop in ontology.get("properties", []):
        name, label = _property_name_and_label(prop)
        sources = _find_sources(name, label, records, source_file)

        item = {
            "ontology_type": "property",
            "ontology_name": name,
            "ontology_label": label,
            "sources": sources,
        }

        if isinstance(prop, dict):
            item["domain"] = prop.get("domain", "")
            item["range"] = prop.get("range", "")

        trace_items.append(item)

    # 3. 关系溯源
    for rel in ontology.get("relations", []):
        if not isinstance(rel, dict):
            continue

        subject = _text(rel.get("subject") or rel.get("source"))
        predicate = _text(rel.get("predicate") or rel.get("type") or rel.get("relation"))
        obj = _text(rel.get("object") or rel.get("target"))

        relation_sources: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str, str, str]] = set()

        for part in (subject, predicate, obj):
            for source in _find_sources(part, part, records, source_file):
                key = _source_key(source)
                if key not in seen:
                    seen.add(key)
                    relation_sources.append(source)

        trace_items.append({
            "ontology_type": "relation",
            "ontology_name": f"{subject}-{predicate}-{obj}",
            "ontology_label": f"{subject} {predicate} {obj}",
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "sources": relation_sources,
        })

    matched_items = sum(1 for item in trace_items if item.get("sources"))
    unmatched_items = len(trace_items) - matched_items

    trace_map = {
        "source_file": source_file,
        "total_records": len(records),
        "total_trace_items": len(trace_items),
        "matched_items": matched_items,
        "unmatched_items": unmatched_items,
        "items": trace_items,
    }

    trace_file = _save_trace_map(trace_map)
    trace_map["trace_file"] = trace_file

    print("✔ 数据溯源完成:", trace_file)

    return trace_map