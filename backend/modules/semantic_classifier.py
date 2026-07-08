"""Compatibility semantic classifier.

The final ontology identification is handled by the B-layer LLM. This module
keeps the old workflow node alive and only carries structured context forward.
"""

from __future__ import annotations

from typing import Any, Dict


def semantic_classify(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a stable semantic payload without injecting fixed ontology items."""
    if not isinstance(payload, dict):
        payload = {}
    entity_json = payload.get("entity_json", payload)
    clean_data = payload.get("clean_data", {})
    return {
        "entity_json": entity_json if isinstance(entity_json, dict) else {},
        "clean_data": clean_data if isinstance(clean_data, dict) else {},
        "classes": [],
        "properties": [],
        "relations": [],
    }


def classify_entity(entity: Dict[str, Any]) -> Dict[str, str]:
    """Small compatibility helper for older callers."""
    name = str(entity.get("name") or entity.get("label") or "").strip()
    label = str(entity.get("label") or name).strip()
    item_type = str(entity.get("type") or entity.get("semantic_type") or "").lower()
    semantic_type = "property" if item_type in {"field", "property", "attribute"} else "class"
    return {"name": name, "label": label, "type": semantic_type}
