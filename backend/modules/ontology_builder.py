"""Build ontology JSON through the B-layer LLM pipeline."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from backend.ai.llm_service import LLMService
from backend.ai.ontology_generator import OntologyGenerator


def build_ontology(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build ontology from workflow clean_data and attach metadata."""
    if not isinstance(payload, dict):
        return _with_metadata(_empty_ontology(), "rule_fallback", ["Invalid ontology input."])

    clean_data = payload.get("clean_data") if "clean_data" in payload else payload
    generator = OntologyGenerator()
    ontology = generator.generate(clean_data, use_llm=True)

    warnings = list(generator.last_warnings)
    generation_mode = generator.last_generation_mode
    if not ontology.get("relations"):
        warning = "??????????????OWL ????? owl:ObjectProperty?"
        if warning not in warnings:
            warnings.append(warning)
    if generation_mode == "rule_fallback":
        warnings.append("?????? fallback ??????????????")

    result = _with_metadata(ontology, generation_mode, warnings)
    result["stats"] = _stats(result, generation_mode)
    return result


def call_llm(prompt: str) -> str:
    """Compatibility helper required by module interface documents."""
    return LLMService().chat(prompt)


def _with_metadata(ontology: Dict[str, Any], mode: str, warnings: List[str]) -> Dict[str, Any]:
    return {
        "classes": ontology.get("classes", []),
        "properties": ontology.get("properties", []),
        "relations": ontology.get("relations", []),
        "metadata": {"generation_mode": mode},
        "warnings": _dedupe_text(warnings),
    }


def _stats(ontology: Dict[str, Any], mode: str) -> Dict[str, Any]:
    relations = ontology.get("relations", [])
    return {
        "classes": len(ontology.get("classes", [])),
        "datatype_properties": len(ontology.get("properties", [])),
        "object_properties": len(relations),
        "relations": len(relations),
        "generation_mode": mode,
    }


def _dedupe_text(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _empty_ontology() -> Dict[str, Any]:
    return {"classes": [], "properties": [], "relations": []}
