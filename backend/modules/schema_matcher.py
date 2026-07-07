from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List


LEGACY_FIELD_MAP = {
    "code": "id",
    "name": "item_name",
    "field_name": "cn_name",
    "data_type": "data_type",
    "length": "length",
    "description": "description",
    "value_range": "value_space",
}


def match_schema(clean_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize C-layer clean_data so downstream modules consume records first."""
    result = dict(clean_data or {}) if isinstance(clean_data, dict) else {}
    records = result.get("records", []) if isinstance(result.get("records", []), list) else []

    if records:
        normalized_records = [_normalize_record(record) for record in records if isinstance(record, dict)]
        normalized_records = [record for record in normalized_records if _has_identity(record)]
        result["records"] = normalized_records
        result["record_count"] = len(normalized_records)
        result["clean_text"] = json.dumps(normalized_records[:50], ensure_ascii=False, indent=2)
        return result

    tables = result.get("tables", []) if isinstance(result.get("tables", []), list) else []
    normalized_records = []
    for table in tables:
        for row in _records_from_table(table):
            normalized_records.append(_normalize_record(row))

    normalized_records = [record for record in normalized_records if _has_identity(record)]
    result["records"] = normalized_records
    result["record_count"] = len(normalized_records)
    result["clean_text"] = (
        json.dumps(normalized_records[:50], ensure_ascii=False, indent=2)
        if normalized_records
        else str(result.get("unstructured_text") or result.get("raw_text") or "")
    )
    return result


def _normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(record)
    for new_key, old_key in LEGACY_FIELD_MAP.items():
        value = str(normalized.get(new_key) or normalized.get(old_key) or "").strip()
        normalized[new_key] = value
        normalized[old_key] = value
    normalized.setdefault("source", record.get("source", {}))
    normalized.setdefault("source_table", _source_table_name(normalized.get("source")))
    return normalized


def _source_table_name(source: Any) -> str:
    if not isinstance(source, dict):
        return ""
    page = source.get("page")
    table_index = source.get("table_index")
    if page is None and table_index is None:
        return ""
    return f"page_{page}_table_{table_index}"


def _records_from_table(table: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(table, dict):
        rows = table.get("rows", [])
        if rows and isinstance(rows[0], dict):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _has_identity(record: Dict[str, Any]) -> bool:
    return any(str(record.get(key) or "").strip() for key in ("code", "name", "field_name", "id", "item_name", "cn_name"))
