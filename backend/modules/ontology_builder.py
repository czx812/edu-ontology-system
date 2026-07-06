"""Adapter for ontology generation."""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from ai.llm_service import LLMService
from ai.ontology_generator import OntologyGenerator


MAX_LLM_TEXT_CHARS = 30000


def build_ontology(clean_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build ontology JSON from cleaned PDF data."""
    records = clean_data.get("records", []) if isinstance(clean_data, dict) else []
    if records:
        return _build_ontology_from_records(records)

    text = _limit_text(_clean_data_to_text(clean_data))
    return OntologyGenerator().generate(text)


def call_llm(prompt: str) -> str:
    """Call the configured LLM and return raw text."""
    return LLMService().chat(prompt)


def _clean_data_to_text(clean_data: Dict[str, Any]) -> str:
    if not clean_data:
        return ""

    for key in ("clean_text", "raw_text", "text", "content"):
        value = clean_data.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return json.dumps(clean_data, ensure_ascii=False, indent=2)


def _limit_text(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_LLM_TEXT_CHARS:
        return text
    return text[:MAX_LLM_TEXT_CHARS] + "\n\n[Content truncated for LLM request.]"


def _build_ontology_from_records(records: Any) -> Dict[str, Any]:
    classes = []
    properties = []
    relations = []
    seen_classes = set()
    seen_properties = set()
    seen_relations = set()

    for record in records:
        if not isinstance(record, dict):
            continue

        code = _clean_value(record.get("id"))
        label = _clean_value(record.get("cn_name")) or _clean_value(record.get("item_name")) or code
        item_name = _clean_value(record.get("item_name"))
        description = _record_description(record)

        if code and code not in seen_classes:
            seen_classes.add(code)
            classes.append({
                "name": code,
                "label": label,
                "description": description,
            })

        property_name = _property_name(item_name or code)
        if property_name:
            property_key = ("EducationDataElement", property_name)
            if property_key not in seen_properties:
                seen_properties.add(property_key)
                properties.append({
                    "name": property_name,
                    "label": label,
                    "domain": "EducationDataElement",
                    "range": _range_from_record(record),
                    "description": description,
                })

        reference = _clean_value(record.get("reference"))
        if code and reference:
            for target in _extract_reference_codes(reference):
                relation_key = (code, target, "references")
                if relation_key not in seen_relations:
                    seen_relations.add(relation_key)
                    relations.append({
                        "source": code,
                        "target": target,
                        "type": "references",
                        "label": "引用",
                        "description": f"{label} 引用 {target}",
                    })

    if classes:
        classes.insert(0, {
            "name": "EducationDataElement",
            "label": "教育数据元",
            "description": "教育管理信息标准中的数据项。",
        })

    return {
        "classes": classes,
        "properties": properties,
        "relations": relations,
    }


def _clean_value(value: Any) -> str:
    return str(value or "").strip()


def _record_description(record: Dict[str, Any]) -> str:
    parts = []
    item_name = _clean_value(record.get("item_name"))
    code = _clean_value(record.get("id"))
    description = _clean_value(record.get("description"))
    value_space = _clean_value(record.get("value_space"))

    if item_name or code:
        parts.append("（".join(part for part in (item_name, code) if part) + ("）" if item_name and code else ""))
    if description:
        parts.append(description)
    if value_space:
        parts.append(f"值空间：{value_space}")
    return "；".join(parts)


def _property_name(name: str) -> str:
    name = _clean_value(name)
    if not name:
        return ""
    name = re.sub(r"\W+", "_", name, flags=re.UNICODE).strip("_")
    return name or ""


def _range_from_record(record: Dict[str, Any]) -> str:
    data_type = _clean_value(record.get("data_type")).upper()
    if data_type == "N":
        return "decimal"
    if data_type in {"D", "DATE"}:
        return "date"
    if data_type in {"B", "BOOLEAN"}:
        return "boolean"
    return "string"


def _extract_reference_codes(reference: str) -> list[str]:
    return re.findall(r"[A-Z]{2,}[A-Z0-9]*\d{4,}", reference)
