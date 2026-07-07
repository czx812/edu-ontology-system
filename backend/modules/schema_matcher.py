from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

STANDARD_COLUMNS = [
    "\u7f16\u53f7",
    "\u6570\u636e\u9879\u540d",
    "\u4e2d\u6587\u7b80\u79f0",
    "\u7c7b\u578b",
    "\u957f\u5ea6",
    "\u7ea6\u675f",
    "\u503c\u7a7a\u95f4",
    "\u89e3\u91ca/\u4e3e\u4f8b",
    "\u5f15\u7528\u7f16\u53f7",
]

KEY_ALIASES = {
    "id": "id",
    "code": "id",
    "item_name": "item_name",
    "name": "item_name",
    "cn_name": "cn_name",
    "label": "cn_name",
    "data_type": "data_type",
    "type": "data_type",
    "length": "length",
    "constraint": "constraint",
    "value_space": "value_space",
    "description": "description",
    "reference": "reference",
    STANDARD_COLUMNS[0]: "id",
    STANDARD_COLUMNS[1]: "item_name",
    STANDARD_COLUMNS[2]: "cn_name",
    STANDARD_COLUMNS[3]: "data_type",
    STANDARD_COLUMNS[4]: "length",
    STANDARD_COLUMNS[5]: "constraint",
    STANDARD_COLUMNS[6]: "value_space",
    STANDARD_COLUMNS[7]: "description",
    STANDARD_COLUMNS[8]: "reference",
}


def match_schema(clean_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize C-layer clean_data so B can consume a stable JSON/text contract."""
    tables = clean_data.get("tables", []) if isinstance(clean_data, dict) else []
    normalized_tables = [_normalize_table(table, index) for index, table in enumerate(tables, 1)]
    normalized_tables = [table for table in normalized_tables if table["rows"]]

    records: List[Dict[str, Any]] = []

    source_file = (
        clean_data.get("source_file")
        or clean_data.get("file_path")
        or clean_data.get("source_path")
        or ""
    )

    for table in normalized_tables:
        for row_index, row in enumerate(table["rows"]):
            record = dict(row)

            # 数据溯源需要保留来源信息
            record["source_file"] = source_file
            record["source_table"] = table["title"]
            record["source_row_index"] = row_index

            if record.get("id") or record.get("cn_name") or record.get("item_name"):
                records.append(record)

    result = dict(clean_data or {})
    result["tables"] = normalized_tables
    result["records"] = records
    result["tables_count"] = len(normalized_tables)
    result["clean_text"] = _records_to_text(records, result.get("raw_text", ""))
    return result


def _normalize_table(table: Any, index: int) -> Dict[str, Any]:
    if isinstance(table, dict):
        title = str(table.get("title") or table.get("table_name") or f"table_{index}")
        rows = [_normalize_row(row) for row in table.get("rows", []) if isinstance(row, dict)]
        return {"title": title, "rows": [row for row in rows if _has_content(row)]}

    if isinstance(table, list):
        rows = _rows_from_matrix(table)
        title = _infer_table_title(rows, index)
        return {"title": title, "rows": rows}

    return {"title": f"table_{index}", "rows": []}


def _rows_from_matrix(table: List[Any]) -> List[Dict[str, Any]]:
    if not table:
        return []

    first_row = [str(cell).strip() for cell in _as_list(table[0])]
    if _looks_like_header(first_row):
        header = first_row
        body = table[1:]
    else:
        width = max((len(_as_list(row)) for row in table), default=0)
        header = STANDARD_COLUMNS[:width]
        body = table

    rows = []
    for raw_row in body:
        values = [str(cell).strip() for cell in _as_list(raw_row)]
        mapped = {
            _canonical_key(header[position]): values[position]
            for position in range(min(len(header), len(values)))
            if values[position]
        }
        row = _normalize_row(mapped)
        if _has_content(row):
            rows.append(row)
    return rows


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    values: Dict[str, str] = {}
    for key, value in row.items():
        canonical = _canonical_key(key)
        if canonical:
            values[canonical] = str(value).strip() if value is not None else ""

    return {
        "id": values.get("id", ""),
        "item_name": values.get("item_name", ""),
        "cn_name": values.get("cn_name", ""),
        "data_type": values.get("data_type", ""),
        "length": values.get("length", ""),
        "constraint": values.get("constraint", ""),
        "value_space": values.get("value_space", ""),
        "description": values.get("description", ""),
        "reference": values.get("reference", ""),
    }


def _canonical_key(key: Any) -> str:
    text = str(key).strip().replace("\n", "")
    return KEY_ALIASES.get(text, text)


def _looks_like_header(row: List[str]) -> bool:
    return sum(1 for cell in row if _canonical_key(cell) in KEY_ALIASES.values()) >= 3


def _as_list(row: Any) -> List[Any]:
    if isinstance(row, list):
        return row
    if isinstance(row, tuple):
        return list(row)
    return [row]


def _has_content(row: Dict[str, Any]) -> bool:
    return any(str(value).strip() for value in row.values())


def _infer_table_title(rows: List[Dict[str, Any]], index: int) -> str:
    for row in rows:
        if row.get("id"):
            return " ".join(part for part in (row.get("id"), row.get("cn_name") or row.get("item_name")) if part)
    return f"table_{index}"


def _records_to_text(records: List[Dict[str, Any]], raw_text: str) -> str:
    if records:
        return json.dumps(records, ensure_ascii=False, indent=2)
    return raw_text or ""
