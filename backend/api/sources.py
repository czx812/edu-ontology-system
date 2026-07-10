from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from api.auth import get_current_user
from config import settings
from services.log_service import list_my_generations


router = APIRouter(prefix="/sources", tags=["sources"])


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_latest_ontology(user_id: str, ontology_file: str = "") -> dict:
    candidates: list[Path] = []
    if ontology_file:
        path = Path(ontology_file)
        candidates.extend([path, settings.EXPORT_DIR / str(user_id) / path.name, settings.EXPORT_DIR / path.name])
    user_dir = settings.EXPORT_DIR / str(user_id)
    if user_dir.exists():
        candidates.extend(sorted(user_dir.glob("merged_ontology_*.json"), key=lambda p: p.stat().st_mtime, reverse=True))
        candidates.extend(sorted(user_dir.glob("*_ontology_*.json"), key=lambda p: p.stat().st_mtime, reverse=True))
    candidates.extend(sorted(settings.EXPORT_DIR.glob("merged_ontology_*.json"), key=lambda p: p.stat().st_mtime, reverse=True))
    for path in candidates:
        try:
            if path.exists() and path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


@router.get("/search")
def search_sources(
    keyword: str = Query(""),
    scope: str = Query("all"),
    filename: str = Query(""),
    ontology_file: str = Query(""),
    user: dict = Depends(get_current_user),
) -> dict:
    # Structured clean_data retains the standard code/name relationship which
    # is intentionally independent of the generated ontology's internal IDs.
    items = _index_structured_sources(user)
    ontology = _load_latest_ontology(str(user["id"]), ontology_file)
    if not items:
        items = _index_ontology(ontology)
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
    return {
        "items": filtered,  # legacy field consumed by older clients
        "sources": filtered,
        "total": len(filtered),
        "ontology_file": ontology_file,
        "stats": ontology.get("stats", {}) if isinstance(ontology, dict) else {},
    }


def _index_structured_sources(user: dict) -> list[dict]:
    """Read a user's saved clean_data files and expose document-derived items."""
    indexed: dict[str, dict] = {}
    for generation in list_my_generations(user):
        data = _load_structured_file(generation.get("structured_file", ""))
        if not data:
            continue
        source_file = Path(str(data.get("source_file") or generation.get("file_path") or generation.get("file_name") or "")).name
        classes = data.get("data_classes", []) if isinstance(data.get("data_classes"), list) else []
        class_names = {str(item.get("code")): str(item.get("name") or "") for item in classes if isinstance(item, dict)}
        for item in [*classes, *(data.get("data_properties", []) if isinstance(data.get("data_properties"), list) else [])]:
            if not isinstance(item, dict) or not _text(item.get("code")):
                continue
            code = _text(item.get("code"))
            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            filename = source.get("file") or source_file
            parent_code = _text(item.get("parent"))
            row = {
                "key": f"standard-{code}", "type_key": "class" if item.get("type") == "数据子类" else "property",
                "type": item.get("type") or "数据属性", "code": code, "name": _text(item.get("name")),
                "label": _text(item.get("name")), "parent": parent_code,
                "parent_name": class_names.get(parent_code, parent_code), "domain": class_names.get(parent_code, ""),
                "source_file": filename, "filename": filename, "source_files": [source.get("file_path") or str(data.get("source_file") or "")],
                "source": {"file": filename, "page": source.get("page")}, "sources": [source],
                "page": source.get("page"), "description": "",
            }
            # Most recent generated file wins; a code is only displayed once.
            indexed.setdefault(code, row)
    return sorted(indexed.values(), key=lambda item: (item["code"], item["type_key"]))


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


def _index_ontology(ontology: dict) -> list[dict]:
    if not isinstance(ontology, dict):
        return []
    result: list[dict] = []
    for cls in ontology.get("classes", []) or []:
        if isinstance(cls, dict):
            result.append(_row("class", "类", cls, cls.get("id") or cls.get("name"), cls.get("label"), cls.get("parent") or cls.get("domain")))
    for prop in ontology.get("datatype_properties") or ontology.get("properties") or []:
        if isinstance(prop, dict):
            result.append(_row("property", "属性", prop, prop.get("code") or prop.get("source_code") or prop.get("id"), prop.get("label") or prop.get("name"), prop.get("domain")))
    for rel in ontology.get("relations", []) or []:
        if isinstance(rel, dict):
            name = f"{rel.get('source') or rel.get('subject')} -> {rel.get('target') or rel.get('object')}"
            result.append(_row("relation", "关系", rel, rel.get("type") or rel.get("predicate"), name, rel.get("type") or rel.get("predicate")))
    for source in ontology.get("metadata", {}).get("source_files", []) if isinstance(ontology.get("metadata", {}), dict) else []:
        result.append({"key": f"source-{source}", "type_key": "source", "type": "来源文件", "name": Path(str(source)).name, "label": Path(str(source)).name, "domain": "", "source": str(source), "source_files": [str(source)], "description": ""})
    return result


def _row(type_key: str, type_label: str, item: dict, code: Any, label: Any, domain: Any) -> dict:
    sources = _sources(item)
    source_files = item.get("source_files") if isinstance(item.get("source_files"), list) else []
    for source in sources:
        value = source.get("file_path") or source.get("source_file")
        if value and value not in source_files:
            source_files.append(value)
    filename = ", ".join(_dedupe([source.get("filename") or Path(str(source.get("file_path") or source.get("source_file") or "")).name for source in sources if isinstance(source, dict)]))
    return {
        "key": f"{type_key}-{code or label}-{len(sources)}",
        "type_key": type_key,
        "type": type_label,
        "code": code or "",
        "name": f"{code or ''} {label or ''}".strip(),
        "label": label or "",
        "domain": domain or "",
        "source": "; ".join(_dedupe([str(item) for item in source_files if item])),
        "source_files": source_files,
        "filename": filename,
        "sources": sources,
        "page": ", ".join(_dedupe([str(source.get("page")) for source in sources if source.get("page") not in (None, "")])),
        "table_index": ", ".join(_dedupe([str(source.get("table_index")) for source in sources if source.get("table_index") not in (None, "")])),
        "row_index": ", ".join(_dedupe([str(source.get("row_index")) for source in sources if source.get("row_index") not in (None, "")])),
        "reference_code": item.get("reference_code") or item.get("reference_id") or "",
        "description": item.get("description") or item.get("field_name") or "",
    }


def _sources(item: dict) -> list[dict]:
    result = []
    if isinstance(item.get("source"), dict):
        result.append(item["source"])
    if isinstance(item.get("sources"), list):
        result.extend([source for source in item["sources"] if isinstance(source, dict)])
    return result


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        text = _text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
