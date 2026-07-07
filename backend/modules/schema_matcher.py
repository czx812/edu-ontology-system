from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List


STANDARD_COLUMNS = [
    "编号",
    "数据项名",
    "中文简称",
    "类型",
    "长度",
    "约束",
    "值空间",
    "解释/举例",
    "引用编号",
]

KEY_ALIASES = {
    "id": "id",
    "code": "id",
    "编号": "id",
    "item_name": "item_name",
    "name": "item_name",
    "数据项名": "item_name",
    "cn_name": "cn_name",
    "label": "cn_name",
    "中文简称": "cn_name",
    "short_name": "short_name",
    "data_type": "data_type",
    "type": "data_type",
    "类型": "data_type",
    "length": "length",
    "长度": "length",
    "constraint": "constraint",
    "约束": "constraint",
    "value_space": "value_space",
    "值空间": "value_space",
    "description": "description",
    "解释/举例": "description",
    "reference": "reference",
    "引用编号": "reference",
    "source_table": "source_table",
    "source_section": "source_section",
}


def match_schema(clean_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize C-layer clean_data so B receives a stable JSON contract."""
    if not isinstance(clean_data, dict):
        clean_data = {"clean_text": str(clean_data or "")}

    records = [_normalize_row(row) for row in _as_dicts(clean_data.get("records", []))]
    records = [record for record in records if _record_has_content(record)]

    if not records:
        tables = clean_data.get("tables", [])
        normalized_tables = [_normalize_table(table, index) for index, table in enumerate(tables, 1)]
        records = []
        for table in normalized_tables:
            for row in table["rows"]:
                row["source_table"] = row.get("source_table") or table["title"]
                records.append(row)
    else:
        normalized_tables = clean_data.get("tables", [])

    for record in records:
        record["candidate_domains"] = _candidate_domains(record)

    result = dict(clean_data)
    result["tables"] = normalized_tables
    result["records"] = records
    result["records_count"] = len(records)
    result["tables_count"] = len(normalized_tables)
    result["clean_text"] = _records_to_text(records, result.get("clean_text") or result.get("raw_text") or "")
    return result


def _normalize_table(table: Any, index: int) -> Dict[str, Any]:
    if isinstance(table, dict):
        title = str(table.get("title") or table.get("table_name") or f"table_{index}")
        rows = [_normalize_row(row) for row in _as_dicts(table.get("rows", []))]
        return {"title": title, "rows": [row for row in rows if _record_has_content(row)]}

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
        if _record_has_content(row):
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
        "short_name": values.get("short_name", ""),
        "data_type": values.get("data_type", ""),
        "length": values.get("length", ""),
        "constraint": values.get("constraint", ""),
        "value_space": values.get("value_space", ""),
        "description": values.get("description", ""),
        "reference": values.get("reference", ""),
        "source_table": values.get("source_table", ""),
        "source_section": values.get("source_section", ""),
    }


def _candidate_domains(record: Dict[str, Any]) -> List[str]:
    text = " ".join(str(record.get(key) or "") for key in ("id", "source_table", "source_section", "cn_name", "item_name", "description"))
    code = str(record.get("id") or "").upper()
    if code.startswith("JCXX"):
        return ["School", "Campus", "Class", "Grade"]
    if code.startswith("JCXS"):
        return ["Student", "Enrollment", "StudentStatus", "Score", "Reward", "Punishment", "Graduation"]
    if code.startswith("JCJG"):
        return ["Teacher", "Staff", "Position", "ProfessionalTitle", "Assessment", "Training"]
    if code.startswith("JCBX"):
        return ["FinanceItem", "Building", "Room", "Facility", "Instrument", "Book", "Journal", "Laboratory", "Experiment"]
    if code.startswith("JCTB"):
        return ["ContactInfo", "TimeInfo", "Organization", "Course", "Major", "Person"]
    if "学校" in text:
        return ["School"]
    if "学生" in text:
        return ["Student"]
    if "教师" in text or "教职工" in text:
        return ["Teacher", "Staff"]
    if "课程" in text:
        return ["Course"]
    return ["EducationResource"]


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


def _as_dicts(items: Any) -> Iterable[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _record_has_content(row: Dict[str, Any]) -> bool:
    label = str(row.get("cn_name") or row.get("item_name") or row.get("id") or "").strip()
    if label in {"码", "号", "称", "位", "期", "箱", "女", "话"}:
        return False
    return any(str(value).strip() for value in row.values())


def _infer_table_title(rows: List[Dict[str, Any]], index: int) -> str:
    for row in rows:
        if row.get("source_table"):
            return row["source_table"]
        if row.get("id"):
            return " ".join(part for part in (row.get("id"), row.get("cn_name") or row.get("item_name")) if part)
    return f"table_{index}"


def _records_to_text(records: List[Dict[str, Any]], clean_text: str) -> str:
    if records:
        return json.dumps(records, ensure_ascii=False, indent=2)
    return clean_text or ""
