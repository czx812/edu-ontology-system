from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Union

import pdfplumber

from utils.file_utils import logger


State = Dict[str, Any]


def _clean_cell(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _append_error(state: State, message: str) -> None:
    errors = state.setdefault("errors", [])
    if isinstance(errors, list):
        errors.append(message)
    else:
        state["errors"] = [str(errors), message]


def parse_pdf(state: State) -> State:
    """Extract raw text and page tables from state['file_path']."""
    start_time = time.time()
    print("[PDF解析] 开始")

    file_path = str(state.get("file_path") or "")
    state.setdefault("raw_text", "")
    state.setdefault("tables", [])

    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file does not exist: {file_path}")

        pages_text: List[str] = []
        tables: List[Dict[str, Any]] = []

        with pdfplumber.open(str(path)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages_text.append(f"[Page {page_number}]\n{text}".strip())

                try:
                    page_tables = page.extract_tables() or []
                except Exception as exc:  # best-effort table extraction per page
                    _append_error(state, f"PDF page {page_number} table extraction failed: {exc}")
                    logger.warning(f"PDF page {page_number} table extraction failed: {exc}")
                    page_tables = []

                for table_index, table in enumerate(page_tables):
                    rows = [
                        [_clean_cell(cell) for cell in (row or [])]
                        for row in (table or [])
                    ]
                    rows = [row for row in rows if any(cell for cell in row)]
                    if rows:
                        tables.append({
                            "page": page_number,
                            "table_index": table_index,
                            "rows": rows,
                        })

        state["raw_text"] = "\n\n".join(part for part in pages_text if part).strip()
        state["tables"] = tables
        elapsed = time.time() - start_time
        print(
            f"[PDF解析] 完成，共解析 {len(pages_text)} 页，"
            f"提取 {len(tables)} 个表格，耗时 {elapsed:.2f} 秒"
        )
        logger.info(
            "PDF extraction completed: %s, pages=%s, tables=%s",
            file_path,
            len(pages_text),
            len(tables),
        )
    except Exception as exc:
        message = f"PDF解析失败: {exc}"
        _append_error(state, message)
        print(f"[PDF解析] {message}")
        logger.exception(message)

    return state


def extract_pdf(payload: Union[str, State]) -> Union[str, State]:
    """Backward-compatible wrapper.

    Existing callers may pass a file path and expect raw text. The workflow now
    passes state and receives state with raw_text/tables populated.
    """
    if isinstance(payload, dict):
        return parse_pdf(payload)

    state: State = {"file_path": str(payload), "raw_text": "", "tables": []}
    parse_pdf(state)
    return str(state.get("raw_text") or "")
