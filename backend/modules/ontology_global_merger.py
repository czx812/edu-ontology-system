from __future__ import annotations

import json
from typing import Any, Dict, List

from backend.ai.llm_service import LLMService
from backend.modules.ontology_aligner import align_multiple_ontologies


def merge_ontology_programmatically(partial_ontologies: list) -> dict:
    merged = {
        "classes": [],
        "properties": [],
        "datatype_properties": [],
        "object_properties": [],
        "relations": [],
        "class_hierarchy": [],
    }
    for ontology in partial_ontologies if isinstance(partial_ontologies, list) else []:
        if not isinstance(ontology, dict):
            continue
        for key in merged:
            values = ontology.get(key, [])
            if isinstance(values, list):
                merged[key].extend(values)
    merged["classes"] = _dedupe(merged["classes"], ("id", "name", "label"))
    datatype = merged["datatype_properties"] or merged["properties"]
    merged["datatype_properties"] = _dedupe(datatype, ("id", "name", "domain", "label"))
    merged["properties"] = merged["datatype_properties"]
    merged["object_properties"] = _dedupe(merged["object_properties"], ("id", "predicate", "domain", "range"))
    merged["relations"] = _dedupe([*merged["relations"], *_relations_from_object_properties(merged["object_properties"])], ("subject", "source", "predicate", "type", "object", "target"))
    merged["class_hierarchy"] = _dedupe(merged["class_hierarchy"], ("parent", "child"))
    return merged


def align_and_merge_ontologies(ontologies: list, source_docs: list | None = None) -> dict:
    return align_multiple_ontologies(ontologies, source_docs=source_docs)


def merge_ontology_with_llm(partial_ontologies: list, document_structure: dict, llm_service: LLMService | None = None) -> dict:
    service = llm_service or LLMService()
    base = merge_ontology_programmatically(partial_ontologies)
    prompt = (
        "You are merging partial education ontology JSON objects. Return strict JSON only. "
        "Keep source_record_ids and evidence. Do not invent sources. Normalize duplicate classes, "
        "datatype_properties, object_properties, relations, and class_hierarchy.\\n\\n"
        f"document_structure={json.dumps(_compact_structure(document_structure), ensure_ascii=False)}\\n"
        f"partial_ontology={json.dumps(base, ensure_ascii=False)[:50000]}"
    )
    result = service.chat_json(prompt, temperature=0.0)
    return merge_ontology_programmatically([base, result])


def _relations_from_object_properties(items: List[Any]) -> List[dict]:
    relations = []
    for item in items:
        if not isinstance(item, dict):
            continue
        subject = item.get("domain") or item.get("source")
        obj = item.get("range") or item.get("target")
        predicate = item.get("id") or item.get("name") or item.get("predicate")
        if subject and obj and predicate:
            relations.append({
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "source_record_ids": item.get("source_record_ids", []),
                "evidence": item.get("evidence", []),
            })
    return relations


def _dedupe(items: List[Any], keys: tuple[str, ...]) -> List[dict]:
    seen = set()
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        marker = tuple(str(item.get(key) or "").lower() for key in keys)
        marker = tuple(part for part in marker if part)
        if not marker:
            marker = (json.dumps(item, ensure_ascii=False, sort_keys=True)[:160],)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def _compact_structure(document_structure: dict) -> dict:
    if not isinstance(document_structure, dict):
        return {}
    return {
        "document_title": document_structure.get("document_title"),
        "document_type": document_structure.get("document_type"),
        "section_hierarchy": document_structure.get("section_hierarchy", [])[:50],
        "relation_clues": document_structure.get("relation_clues", [])[:80],
        "detected_patterns": document_structure.get("detected_patterns", []),
    }
