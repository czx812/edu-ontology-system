"""Document-driven standard metadata extraction.

This adapter exposes a stable ``extract`` API while keeping the parser
independent from the generated ontology.
"""

from __future__ import annotations

from typing import Any, Iterable

from modules.source_parser import clean_label, parse_source


def extract(raw_text: str, tables: Iterable[Any] | None = None) -> dict:
    parsed = parse_source(raw_text, tables)
    classes = [{**item, "name": clean_label(item.get("name")), "label": clean_label(item.get("label") or item.get("name"))} for item in parsed.get("classes", [])]
    properties = [{**item, "name": clean_label(item.get("name")), "label": clean_label(item.get("label") or item.get("name"))} for item in parsed.get("properties", [])]
    return {"classes": classes, "properties": properties, "relations": []}
