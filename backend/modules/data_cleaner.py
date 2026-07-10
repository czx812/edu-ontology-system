from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union

from config import settings
from modules.standard_mapper import map_standard_codes
from utils.file_utils import logger


State = Dict[str, Any]
STANDARD_FIELDS = [
    "code",
    "name",
    "field_name",
    "data_type",
    "length",
    "description",
    "value_range",
    "reference",
]

HEADER_ALIASES = {
    "编号": "code",
    "数据元编号": "code",
    "代码": "code",
    "标识符": "code",
    "id": "code",
    "code": "code",
    "中文名称": "name",
    "名称": "name",
    "数据元名称": "name",
    "数据项名": "name",
    "中文简称": "name",
    "name": "name",
    "label": "name",
    "英文名称": "field_name",
    "字段名": "field_name",
    "字段名称": "field_name",
    "标识": "field_name",
    "field": "field_name",
    "fieldname": "field_name",
    "field_name": "field_name",
    "数据类型": "data_type",
    "类型": "data_type",
    "data_type": "data_type",
    "datatype": "data_type",
    "type": "data_type",
    "数据长度": "length",
    "长度": "length",
    "length": "length",
    "说明": "description",
    "备注": "description",
    "定义": "description",
    "描述": "description",
    "解释/举例": "description",
    "description": "description",
    "值域": "value_range",
    "取值范围": "value_range",
    "值空间": "value_range",
    "value_range": "value_range",
    "valuespace": "value_range",
    "value_space": "value_range",
    "引用编号": "reference",
    "引用号": "reference",
    "引用": "reference",
    "reference": "reference",
    "reference_id": "reference",
}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\n", " ")).strip()


def _header_key(value: Any) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"[\s:：/\\()（）\[\]【】_-]+", "", text)
    return text


def _canonical_header(value: Any) -> str:
    raw = _clean_text(value)
    return HEADER_ALIASES.get(raw) or HEADER_ALIASES.get(_header_key(raw), "")


def _as_rows(table: Any) -> List[List[str]]:
    rows = table.get("rows", []) if isinstance(table, dict) else table
    if not isinstance(rows, list):
        return []
    cleaned: List[List[str]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)):
            continue
        cells = [_clean_text(cell) for cell in row]
        if any(cells):
            cleaned.append(cells)
    return cleaned


def _table_source(table: Any, row_index: int, file_path: str = "") -> Dict[str, Any]:
    filename = Path(file_path).name if file_path else ""
    if not isinstance(table, dict):
        return {"file_path": file_path, "filename": filename, "page": None, "table_index": None, "row_index": row_index}
    return {
        "file_path": file_path,
        "filename": filename,
        "page": table.get("page"),
        "table_index": table.get("table_index"),
        "row_index": row_index,
    }


def _record_key(record: Dict[str, Any]) -> Tuple[str, ...]:
    code = _clean_text(record.get("code"))
    if code:
        return ("code", code.lower())
    return (
        "name_field",
        _clean_text(record.get("name")).lower(),
        _clean_text(record.get("field_name")).lower(),
    )


def _has_identity(record: Dict[str, Any]) -> bool:
    return any(_clean_text(record.get(key)) for key in ("name", "code", "field_name"))


def _build_records_from_tables(tables: Iterable[Any], file_path: str = "") -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen = set()

    for table in tables or []:
        rows = _as_rows(table)
        if not rows:
            continue

        header = rows[0]
        mapped_headers = [_canonical_header(cell) for cell in header]
        if not any(mapped_headers):
            continue

        for row_index, row in enumerate(rows[1:], start=1):
            record = {field: "" for field in STANDARD_FIELDS}
            for column_index, canonical in enumerate(mapped_headers):
                if not canonical or column_index >= len(row):
                    continue
                value = _clean_text(row[column_index])
                if value:
                    record[canonical] = value

            if not _has_identity(record):
                continue

            key = _record_key(record)
            if key in seen:
                continue
            seen.add(key)
            record["source"] = _table_source(table, row_index, file_path)
            record["source_file"] = file_path
            records.append(record)

    return records


def _structured_path() -> Path:
    settings.STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return settings.STRUCTURED_DIR / f"structured_{timestamp}.json"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(settings.PROJECT_DIR)).replace("\\", "/")
    except ValueError:
        return str(path)


def _save_clean_data(cleaned: Dict[str, Any]) -> str:
    output_path = _structured_path()
    output_path.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    display_path = _display_path(output_path)
    print(f"[数据清洗] 结构化JSON已保存: {display_path}")
    logger.info("Structured data saved: %s", output_path)
    return display_path


def clean_data(payload: Union[State, str]) -> Union[State, Dict[str, Any]]:
    """Generate stable structured clean_data from PDF tables and text."""
    start_time = time.time()
    print("[数据清洗] 开始")

    state_input = isinstance(payload, dict)
    state: State = payload if state_input else {"raw_text": str(payload or ""), "tables": []}
    raw_text = str(state.get("raw_text") or "")
    tables = state.get("tables") or []

    file_path = str(state.get("file_path") or "")
    records = _build_records_from_tables(tables, file_path)
    semantic_items = map_standard_codes(tables, raw_text, file_path)
    cleaned = {
        "source_file": str(state.get("file_path") or ""),
        "raw_text": raw_text,
        "tables": tables,
        "record_count": len(records),
        "records": records,
        "unstructured_text": raw_text[:3000],
        **semantic_items,
    }

    state["clean_data"] = cleaned
    state["structured_file"] = _save_clean_data(cleaned)

    elapsed = time.time() - start_time
    print(f"[数据清洗] 生成结构化记录 {len(records)} 条，耗时 {elapsed:.2f} 秒")
    logger.info("Data cleaning completed, records=%s", len(records))

    return state if state_input else cleaned


