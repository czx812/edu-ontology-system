from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from config import settings


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _record_text(record: Dict[str, Any]) -> str:
    """
    把一条结构化数据拼成可检索文本。
    """
    fields = [
        record.get("id", ""),
        record.get("item_name", ""),
        record.get("cn_name", ""),
        record.get("description", ""),
        record.get("reference", ""),
        record.get("value_space", ""),
        record.get("source_table", ""),
    ]
    return " ".join(str(x) for x in fields if x).lower()


def _keywords(name: str, label: str) -> List[str]:
    """
    本体元素可能有英文名、中文标签，都拿来匹配。
    """
    result = []

    for value in (name, label):
        value = str(value or "").strip()
        if value and value not in result:
            result.append(value)

    return result


def _match_record(name: str, label: str, record: Dict[str, Any]) -> bool:
    """
    判断一个本体元素是否能匹配到某条结构化数据。
    """

    record_all_text = _record_text(record)

    record_id = _norm(record.get("id"))
    record_item_name = _norm(record.get("item_name"))
    record_cn_name = _norm(record.get("cn_name"))

    for word in _keywords(name, label):
        key = _norm(word)

        if not key:
            continue

        # 精确匹配：最可靠
        if key in {record_id, record_item_name, record_cn_name}:
            return True

        # 包含匹配：兼容 LLM 生成的名称略有差异
        if key in record_all_text:
            return True

        if record_cn_name and record_cn_name in key:
            return True

        if record_item_name and record_item_name in key:
            return True

    return False


def _source_key(source: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return (
        str(source.get("source_file", "")),
        str(source.get("source_table", "")),
        str(source.get("source_row_index", "")),
        str(source.get("id", "")),
    )


def _find_sources(name: str, label: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据本体元素名称，在 records 中找来源。
    """

    sources: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str, str]] = set()

    for record in records:
        if not _match_record(name, label, record):
            continue

        source = {
            "source_file": record.get("source_file", ""),
            "source_table": record.get("source_table", ""),
            "source_row_index": record.get("source_row_index", ""),

            "id": record.get("id", ""),
            "item_name": record.get("item_name", ""),
            "cn_name": record.get("cn_name", ""),
            "data_type": record.get("data_type", ""),
            "length": record.get("length", ""),
            "constraint": record.get("constraint", ""),
            "value_space": record.get("value_space", ""),
            "description": record.get("description", ""),
            "reference": record.get("reference", ""),
        }

        key = _source_key(source)

        if key not in seen:
            seen.add(key)
            sources.append(source)

    return sources


def _class_name_and_label(item: Any) -> Tuple[str, str]:
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("id") or item.get("label") or "").strip()
        label = str(item.get("label") or item.get("cn_name") or name).strip()
    else:
        name = str(item).strip()
        label = name

    return name, label


def _property_name_and_label(item: Any) -> Tuple[str, str]:
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("id") or item.get("item_name") or "").strip()
        label = str(item.get("label") or item.get("cn_name") or name).strip()
    else:
        name = str(item).strip()
        label = name

    return name, label


def _save_trace_map(trace_map: Dict[str, Any]) -> str:
    """
    把溯源结果单独保存成 JSON 文件。
    """
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
    数据溯源模块。

    输入：
    clean_data：schema_matcher 之后的数据
    ontology：ontology_aligner 之后的本体

    输出：
    trace_map：本体元素 -> 结构化数据来源 的映射
    """

    records = clean_data.get("records", []) if isinstance(clean_data, dict) else []

    trace_items: List[Dict[str, Any]] = []

    # 1. 类的溯源
    for cls in ontology.get("classes", []):
        name, label = _class_name_and_label(cls)
        sources = _find_sources(name, label, records)

        trace_items.append({
            "ontology_type": "class",
            "ontology_name": name,
            "ontology_label": label,
            "sources": sources,
        })

    # 2. 属性的溯源
    for prop in ontology.get("properties", []):
        name, label = _property_name_and_label(prop)
        sources = _find_sources(name, label, records)

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

    # 3. 关系的溯源
    for rel in ontology.get("relations", []):
        if not isinstance(rel, dict):
            continue

        subject = str(rel.get("subject", "")).strip()
        predicate = str(
            rel.get("predicate")
            or rel.get("type")
            or rel.get("relation")
            or ""
        ).strip()
        obj = str(rel.get("object", "")).strip()

        sources: List[Dict[str, Any]] = []
        relation_seen: Set[Tuple[str, str, str, str]] = set()

        for part in (subject, predicate, obj):
            for source in _find_sources(part, part, records):
                key = _source_key(source)
                if key not in relation_seen:
                    relation_seen.add(key)
                    sources.append(source)

        trace_items.append({
            "ontology_type": "relation",
            "ontology_name": f"{subject}-{predicate}-{obj}",
            "ontology_label": f"{subject} {predicate} {obj}",
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "sources": sources,
        })

    matched_items = sum(1 for item in trace_items if item.get("sources"))
    unmatched_items = len(trace_items) - matched_items

    trace_map = {
        "source_file": clean_data.get("source_file", "") if isinstance(clean_data, dict) else "",
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