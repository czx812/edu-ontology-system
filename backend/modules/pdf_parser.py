from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, List

import camelot
import pdfplumber

from utils.file_utils import read_file_bytes, logger


def _clean_cell(value: Any) -> str:
    return " ".join(str(value or "").split())


def _extract_text(file_path: str) -> str:
    pdf_bytes = read_file_bytes(file_path)
    pages: List[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(f"[Page {page_index}]\n{text}")
    return "\n\n".join(pages)


def _extract_tables(file_path: str) -> List[List[List[str]]]:
    tables: List[List[List[str]]] = []
    for flavor in ("lattice", "stream"):
        try:
            for table in camelot.read_pdf(file_path, flavor=flavor, pages="all"):
                rows = [[_clean_cell(cell) for cell in row] for row in table.df.values.tolist()]
                rows = [row for row in rows if any(row)]
                if rows:
                    tables.append(rows)
        except Exception as exc:
            logger.warning(f"Camelot {flavor} extraction skipped: {exc}")
    return tables


def extract_pdf(file_path: str) -> str:
    """Extract plain text and best-effort tables from a PDF."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {file_path}")

    raw_text = _extract_text(str(path))
    tables = _extract_tables(str(path))

    if tables:
        raw_text += "\n\n[Extracted Tables]\n"
        for index, table in enumerate(tables, start=1):
            raw_text += f"\n--- Table {index} ---\n"
            raw_text += "\n".join(" | ".join(row) for row in table)
            raw_text += "\n"

    logger.info(f"PDF extraction completed: {file_path}, tables={len(tables)}")
    return raw_text.strip()
