from __future__ import annotations

import re
from typing import Any, Dict, List

try:
    from utils.file_utils import logger
except ModuleNotFoundError:  # Allows importing as backend.modules.data_cleaner.
    from backend.utils.file_utils import logger


TABLE_MARKER = "[Extracted Tables]"
DATA_CODE_RE = re.compile(r"\b((?:JCTB|JCXX|JCXS|JCJG|JCBX)[A-Z0-9]*\d{4,})\b", re.I)
SECTION_RE = re.compile(r"^\s*(\d+(?:\.\d+)+)\s+(.+?)\s*$")

NOISE_KEYWORDS = (
    "目录",
    "前言",
    "范围",
    "规范性引用文件",
    "术语和定义",
    "本标准依据",
    "中华人民共和国教育行业标准",
    "教育部发布",
)

HEADER_LABELS = {
    "编号",
    "中文简称",
    "数据项名",
    "解释/举例",
    "值空间",
    "引用编号",
    "类型",
    "长度",
    "约束",
}


def clean_data(raw_text: str) -> Dict[str, Any]:
    """Normalize extracted PDF text into C-layer clean_data."""
    text = _normalize_text(raw_text or "")
    text_without_tables, tables = _split_tables(text)
    clean_text = _filter_noise_text(text_without_tables)
    records = _records_from_tables(tables)

    result = {
        "raw_text": text,
        "clean_text": clean_text,
        "tables": tables,
        "records": records,
        "tables_count": len(tables),
        "records_count": len(records),
    }
    logger.info(f"Text cleaning completed, tables={len(tables)}, records={len(records)}")
    return result


def _normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_tables(text: str) -> tuple[str, List[List[List[str]]]]:
    if TABLE_MARKER not in text:
        return text, []

    text_part, table_part = text.split(TABLE_MARKER, 1)
    tables: List[List[List[str]]] = []
    for block in re.split(r"\n--- Table \d+ ---\n", table_part):
        rows: List[List[str]] = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            row = [_clean_cell(cell) for cell in line.split("|")]
            if any(row):
                rows.append(row)
        if rows:
            tables.append(rows)
    return text_part.strip(), tables


def _filter_noise_text(text: str) -> str:
    lines: List[str] = []
    skip_section = False
    for raw_line in text.splitlines():
        line = " ".join(raw_line.strip().split())
        if not line:
            continue
        if line.startswith("[Page "):
            skip_section = False
            continue
        if _is_noise_line(line):
            skip_section = True
            continue
        if skip_section and not DATA_CODE_RE.search(line) and len(line) < 80:
            continue
        skip_section = False
        lines.append(line)
    return "\n".join(lines)


def _records_from_tables(tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    current_section = ""
    current_table = ""
    for table_index, table in enumerate(tables, start=1):
        header = _find_header(table)
        if not header:
            for row in table:
                joined = " ".join(row)
                section = _section_title(joined)
                if section:
                    current_section = section
                    current_table = section
            continue

        header_index, header_row = header
        column_map = [_canonical_header(cell) for cell in header_row]
        for raw_row in table[header_index + 1:]:
            if not any(raw_row):
                continue
            joined = " ".join(raw_row)
            section = _section_title(joined)
            if section:
                current_section = section
                current_table = section
                continue

            row = {
                column_map[index]: raw_row[index].strip()
                for index in range(min(len(column_map), len(raw_row)))
                if column_map[index] and raw_row[index].strip()
            }
            record = _normalize_record(row, current_table or f"table_{table_index}", current_section)
            if record and not _is_noise_record(record):
                records.append(record)
    return _dedupe_records(records)


def _find_header(table: List[List[str]]) -> tuple[int, List[str]] | None:
    for index, row in enumerate(table[:8]):
        score = sum(1 for cell in row if _canonical_header(cell))
        if score >= 3:
            return index, row
    return None


def _canonical_header(value: Any) -> str:
    text = _clean_cell(value).replace(" ", "")
    mapping = {
        "编号": "id",
        "数据项名": "item_name",
        "中文简称": "cn_name",
        "类型": "data_type",
        "长度": "length",
        "约束": "constraint",
        "值空间": "value_space",
        "解释/举例": "description",
        "解释": "description",
        "举例": "description",
        "引用编号": "reference",
    }
    return mapping.get(text, "")


def _normalize_record(row: Dict[str, str], source_table: str, source_section: str) -> Dict[str, Any]:
    record = {
        "id": _clean_cell(row.get("id")),
        "item_name": _clean_cell(row.get("item_name")),
        "cn_name": _clean_cell(row.get("cn_name")),
        "short_name": _clean_cell(row.get("short_name")),
        "data_type": _clean_cell(row.get("data_type")),
        "length": _clean_cell(row.get("length")),
        "constraint": _clean_cell(row.get("constraint")),
        "value_space": _clean_cell(row.get("value_space")),
        "description": _clean_cell(row.get("description")),
        "reference": _clean_cell(row.get("reference")),
        "source_table": source_table,
        "source_section": source_section,
    }
    if not record["id"]:
        match = DATA_CODE_RE.search(" ".join(row.values()))
        if match:
            record["id"] = match.group(1)
    return record


def _section_title(text: str) -> str:
    match = SECTION_RE.match(text)
    if not match:
        return ""
    title = match.group(2).strip()
    if any(word in title for word in NOISE_KEYWORDS):
        return ""
    return f"{match.group(1)} {title}"


def _is_noise_line(line: str) -> bool:
    if any(word == line or line.startswith(word) for word in NOISE_KEYWORDS):
        return True
    if line in HEADER_LABELS:
        return True
    if re.match(r"^\d+$", line):
        return True
    if re.match(r"^(GB/T|JY/T)\s+\S+\s+.+", line) and not DATA_CODE_RE.search(line):
        return True
    return False


def _is_noise_record(record: Dict[str, Any]) -> bool:
    label = record.get("cn_name") or record.get("item_name") or record.get("id") or ""
    label = str(label).strip()
    if not label or label in {"码", "号", "称", "位", "期", "箱", "女", "话"}:
        return True
    if label in HEADER_LABELS:
        return True
    if any(word in label for word in NOISE_KEYWORDS):
        return True
    if not record.get("id") and len(label) <= 1:
        return True
    return False


def _dedupe_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for record in records:
        key = (
            str(record.get("id") or "").lower(),
            str(record.get("cn_name") or record.get("item_name") or "").lower(),
            str(record.get("source_table") or "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def _clean_cell(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())
