from __future__ import annotations

import re
from typing import Any, Dict, List

from utils.file_utils import logger


def _parse_tables(text: str) -> List[List[List[str]]]:
    marker = "[Extracted Tables]"
    if marker not in text:
        return []

    table_block = text.split(marker, 1)[1]
    tables: List[List[List[str]]] = []
    for block in re.split(r"\n--- Table \d+ ---\n", table_block):
        rows: List[List[str]] = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append([cell.strip() for cell in line.split("|")])
        if rows:
            tables.append(rows)
    return tables


def clean_data(raw_text: str) -> Dict[str, Any]:
    """Normalize extracted PDF text into the structure expected downstream."""
    clean_text = re.sub(r"\s{3,}", " ", raw_text or "")
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
    tables = _parse_tables(clean_text)

    logger.info(f"Text cleaning completed, tables={len(tables)}")
    return {
        "raw_text": clean_text,
        "clean_text": clean_text,
        "tables": tables,
    }
