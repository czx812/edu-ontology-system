from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from api.auth import get_current_user
from config import settings
from services.log_service import list_my_generations


router = APIRouter(prefix="/sources", tags=["sources"])


def _text(value: Any) -> str:
    return str(value or "").strip()


@router.get("")
@router.get("/search", include_in_schema=False)
def get_sources(
    keyword: str = Query(""),
    scope: str = Query("all"),
    filename: str = Query(""),
    user: dict = Depends(get_current_user),
) -> dict:
    items = _index_structured_sources(user)
    query = keyword.lower().strip()
    filename_query = filename.lower().strip()
    scope_map = {"class": "class", "property": "property", "relation": "relation", "file": "source"}
    selected = scope_map.get(scope, "")

    def ok(item: dict) -> bool:
        if selected and item.get("type_key") != selected:
            return False
        if filename_query and filename_query not in _text(item.get("source_files")).lower() and filename_query not in _text(item.get("filename")).lower():
            return False
        if not query:
            return True
        blob = " ".join(_text(item.get(key)) for key in ("code", "label", "name", "domain", "description", "source", "source_files", "filename")).lower()
        return query in blob

    filtered = [item for item in items if ok(item)]
    # Keep a matched class together with its attributes so the UI can expand a
    # Chinese-name search result even when attribute names do not repeat it.
    if query and selected in ("", "class", "property"):
        matched_codes = {item.get("code") for item in filtered if item.get("type_key") == "class"}
        matched_parents = {item.get("parent") for item in filtered if item.get("type_key") == "property"}
        filtered = [
            item for item in items
            if ok(item)
            or (not selected and item.get("type_key") == "property" and item.get("parent") in matched_codes)
            or (not selected and item.get("type_key") == "class" and item.get("code") in matched_parents)
        ]
    source_classes = [item for item in filtered if item.get("type_key") == "class"]
    source_properties = [item for item in filtered if item.get("type_key") == "property"]
    classes = [_source_payload(item) for item in source_classes]
    properties = [_source_payload(item) for item in source_properties]
    print("[SOURCE API] not ontology")
    print("classes:")
    for item in classes:
        print(f"{item['code']} {item['name']}")
    print("properties:")
    for item in properties:
        print(f"{item['code']} {item['name']}")
    return {
        "data_type": "source",
        "source_metadata": {
            "classes": classes,
            "properties": properties,
            "relations": [],
        },
        "classes": classes,
        "properties": properties,
    }


def _index_structured_sources(user: dict) -> list[dict]:
    """Read a user's saved clean_data files and expose document-derived items."""
    indexed: dict[str, dict] = {}
    for generation in list_my_generations(user):
        data = _load_structured_file(generation.get("structured_file", ""))
        if not data:
            continue
        metadata = data.get("standard_metadata") if isinstance(data.get("standard_metadata"), dict) else None
        if metadata is not None:
            _append_metadata_rows(indexed, metadata, Path(str(data.get("source_file") or generation.get("file_path") or generation.get("file_name") or "")).name)
    if not indexed:
        cache = settings.DATA_DIR / "cache" / "source_metadata.json"
        data = _load_structured_file(str(cache))
        metadata = data.get("standard_metadata", data) if isinstance(data, dict) else {}
        if isinstance(metadata, dict):
            _append_metadata_rows(indexed, metadata, "")
    return sorted(indexed.values(), key=lambda item: (item["code"], item["type_key"]))


def _append_metadata_rows(indexed: dict[str, dict], metadata: dict, source_file: str) -> None:
    classes = [item for item in metadata.get("classes", []) if _valid_standard_item(item, "数据子类")]
    class_names = {str(item["code"]): str(item.get("name") or "") for item in classes}
    properties = [item for item in metadata.get("properties", []) if _valid_standard_item(item, "数据属性")]
    for item in [*classes, *properties]:
        code = _text(item["code"])
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        parent = _text(item.get("parent"))
        filename = source.get("file") or source_file
        indexed.setdefault(code, {
            "key": f"standard-{code}", "type_key": "class" if item.get("type") == "数据子类" else "property",
            "type": item.get("type"), "code": code, "name": _text(item.get("name")),
            "label": _text(item.get("name")), "parent": parent,
            "parent_name": class_names.get(parent, parent), "domain": class_names.get(parent, ""),
            "source_file": filename, "filename": filename, "source_files": [source.get("file_path") or source_file],
            "source": {"file": filename, "page": source.get("page")}, "sources": [source],
            "page": source.get("page"), "description": "",
        })


def _load_structured_file(value: str) -> dict:
    if not value:
        return {}
    path = Path(value)
    candidates = [path, settings.PROJECT_DIR / path]
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception:
            continue
    return {}


def _source_payload(item: dict) -> dict:
    """Return only the PDF-standard fields exposed by the source endpoint."""
    return {
        "code": _text(item.get("code")),
        "name": _text(item.get("name")),
        "type": _text(item.get("type")),
        "parent": _text(item.get("parent")),
    }


_STANDARD_CODE = re.compile(r"^[A-Z]{2,}[A-Z0-9]*\d{4,}$")


def _valid_standard_item(item: Any, expected_type: str) -> bool:
    """Accept only genuine uppercase education-standard code records."""
    if not isinstance(item, dict):
        return False
    code = _text(item.get("code"))
    return bool(code and code.isupper() and _STANDARD_CODE.fullmatch(code) and item.get("type") == expected_type)
