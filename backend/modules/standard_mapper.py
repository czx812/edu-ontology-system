"""Extract semantic meanings for education-standard codes from parsed PDF content.

The mapper deliberately learns names from a document's text/tables.  It does
not contain a catalogue of individual codes, so the same logic works for
JCTB, XXZZ, XZGJ and other standard-code families.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


CODE_RE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*\d{4,})\b")
CLASS_SUFFIX_RE = re.compile(r"(?:数据(?:子)?类(?:表)?|信息类|代码表)\s*$")


def map_standard_codes(tables: Iterable[Any], raw_text: str = "", file_path: str = "") -> Dict[str, List[Dict[str, Any]]]:
    """Return document-derived data classes and data properties with provenance."""
    filename = Path(file_path).name
    classes: Dict[str, Dict[str, Any]] = {}
    properties: Dict[str, Dict[str, Any]] = {}

    # A table title normally contains ``表n | CODE | 中文名称数据子类表``.
    for table in tables or []:
        if not isinstance(table, dict):
            continue
        source = _source(table, filename, file_path)
        rows = table.get("rows") or []
        table_class = _class_from_rows(rows, source)
        if table_class:
            classes.setdefault(table_class["code"], table_class)
        for row_index, row in enumerate(rows):
            item = _property_from_row(row, table_class and table_class["code"], source, row_index)
            if item:
                properties.setdefault(item["code"], item)

    # Text covers PDFs whose table detector did not recognise a table title.
    page = None
    for line in str(raw_text or "").splitlines():
        marker = re.match(r"\[Page\s+(\d+)]", line.strip(), re.I)
        if marker:
            page = int(marker.group(1))
            continue
        item = _class_from_text(line, _source({"page": page}, filename, file_path))
        if item:
            classes.setdefault(item["code"], item)

    # Resolve parents only after all classes are known. Longest prefix wins.
    for prop in properties.values():
        parent = _parent_code(prop["code"], classes, prop.get("parent", ""))
        if parent:
            prop["parent"] = parent
        else:
            prop.pop("parent", None)

    return {
        "data_classes": sorted(classes.values(), key=lambda item: item["code"]),
        "data_properties": sorted(properties.values(), key=lambda item: item["code"]),
    }


def _source(table: Dict[str, Any], filename: str, file_path: str) -> Dict[str, Any]:
    source = {"file": filename, "page": table.get("page")}
    if file_path:
        source["file_path"] = file_path
    return source


def _class_from_rows(rows: Iterable[Any], source: Dict[str, Any]) -> Dict[str, Any] | None:
    for row in rows or []:
        text = " | ".join(_text(cell) for cell in row if _text(cell))
        item = _class_from_text(text, source)
        if item:
            return item
    return None


def _class_from_text(text: str, source: Dict[str, Any]) -> Dict[str, Any] | None:
    clean = _text(text)
    match = CODE_RE.search(clean)
    if not match or not CLASS_SUFFIX_RE.search(clean):
        return None
    code = match.group(1)
    tail = clean[match.end():].strip(" |:：-—")
    tail = re.sub(r"^(?:表\s*\d+\s*[|｜])?", "", tail)
    # Stop at a table column separator, but retain the Chinese title itself.
    name = tail.split("|", 1)[0].strip()
    if not name or not CLASS_SUFFIX_RE.search(name):
        return None
    if not name.endswith("表"):
        name += "表"
    return {"code": code, "name": name, "type": "数据子类", "source": dict(source)}


def _property_from_row(row: Any, table_parent: str | None, source: Dict[str, Any], row_index: int) -> Dict[str, Any] | None:
    if not isinstance(row, (list, tuple)):
        return None
    cells = [_text(cell) for cell in row]
    code_index = next((i for i, cell in enumerate(cells) if CODE_RE.fullmatch(cell)), None)
    if code_index is None:
        return None
    code = cells[code_index]
    # Ignore a class title embedded in a table; class extraction owns it.
    following = [cell for cell in cells[code_index + 1:] if cell]
    if not following or CLASS_SUFFIX_RE.search(" ".join(following)):
        return None
    field_name = following[0]
    chinese_name = following[1] if len(following) > 1 and _looks_like_name(following[1]) else ""
    name = " ".join(part for part in (field_name, chinese_name) if part)
    if not name:
        return None
    item_source = dict(source)
    item_source["row_index"] = row_index
    item: Dict[str, Any] = {"code": code, "name": name, "type": "数据属性", "source": item_source}
    if table_parent:
        item["parent"] = table_parent
    return item


def _looks_like_name(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value)) and value not in {"M", "O", "C", "T"}


def _parent_code(code: str, classes: Dict[str, Dict[str, Any]], proposed: str) -> str:
    if proposed in classes and code.startswith(proposed):
        return proposed
    matches = [candidate for candidate in classes if code.startswith(candidate) and candidate != code]
    return max(matches, key=len) if matches else ""


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\n", " ")).strip()
