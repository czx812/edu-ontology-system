"""Extract PDF education-standard classes and properties independently."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

CODE_RE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*\d{4,})\b")
CLASS_RE = re.compile(r"(?:数据子类|数据类|信息类)(?:表)?\s*$")


def clean_label(text: Any) -> str:
    """Normalize labels extracted from PDF table boundaries."""
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    before = value
    value = re.sub(r"[。．\)）\(（\]】\[【：:；;，,]+$", "", value).strip()
    value = re.sub(r"^[\)）\(（\]】\[【：:；;，,]+", "", value).strip()
    value = re.sub(r"\s+", " ", value).strip()
    if before != value:
        print(f"标签清洗前：{before}")
        print(f"标签清洗后：{value}")
    return value


def parse_source(raw_text: str, tables: Iterable[Any] | None = None) -> Dict[str, List[Dict[str, str]]]:
    classes: Dict[str, Dict[str, str]] = {}
    properties: Dict[str, Dict[str, str]] = {}
    lines = [str(line or "").strip() for line in str(raw_text or "").splitlines()]
    for line in lines:
        match = CODE_RE.search(line)
        if not match:
            continue
        code = match.group(1)
        name = re.sub(r"^[|｜:：\-\s]+", "", line[match.end():]).strip()
        name = clean_label(re.split(r"[|｜]", name, maxsplit=1)[0])
        if not name:
            continue
        if CLASS_RE.search(name) or (len(code) <= 8 and re.search(r"[\u4e00-\u9fff]", name)):
            classes.setdefault(code, {"code": code, "name": name, "type": "数据子类"})
        elif code not in classes:
            properties.setdefault(code, {"code": code, "name": name, "type": "数据属性"})

    # Table extraction can retain the standard title even when text layout is
    # fragmented; use the same line parser for every non-empty table row.
    for table in tables or []:
        rows = table.get("rows", []) if isinstance(table, dict) else []
        for row in rows:
            if isinstance(row, (list, tuple)):
                parsed = parse_source(" ".join(str(cell or "") for cell in row))
                for item in parsed["classes"]:
                    classes.setdefault(item["code"], item)
                for item in parsed["properties"]:
                    properties.setdefault(item["code"], item)

    class_codes = sorted(classes)
    for code, item in properties.items():
        parents = [candidate for candidate in class_codes if code.startswith(candidate)]
        if parents:
            item["parent"] = max(parents, key=len)
    return {
        "classes": [classes[code] for code in class_codes],
        "properties": [properties[code] for code in sorted(properties)],
        "relations": [],
    }
