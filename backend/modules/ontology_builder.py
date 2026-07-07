"""Build ontology JSON through the B-layer LLM pipeline."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from backend.ai.llm_service import LLMService
from backend.ai.ontology_generator import OntologyGenerator


def build_ontology(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build ontology from workflow payload while keeping the public API stable."""
    if not isinstance(payload, dict):
        return _with_metadata(_empty_ontology(), "rule_fallback", ["输入不是有效 dict，返回空本体。"])

    clean_data = payload.get("clean_data") if "clean_data" in payload else payload
    generator = OntologyGenerator()
    ontology = generator.generate(clean_data, use_llm=True)

    warnings = list(generator.last_warnings)
    generation_mode = generator.last_generation_mode
    if not ontology.get("relations"):
        warning = "当前大模型未识别出对象关系，OWL 中不会生成 owl:ObjectProperty。"
        if warning not in warnings:
            warnings.append(warning)
    if generation_mode == "rule_fallback":
        warnings.append("当前使用规则 fallback 生成，本体语义质量可能较低。")

    result = _with_metadata(ontology, generation_mode, warnings)
    result["stats"] = _stats(result, generation_mode)
    return result


def call_llm(prompt: str) -> str:
    """Compatibility helper required by module interface documents."""
    return LLMService().chat(prompt)


def _with_metadata(ontology: Dict[str, Any], mode: str, warnings: List[str]) -> Dict[str, Any]:
    result = {
        "classes": ontology.get("classes", []),
        "properties": ontology.get("properties", []),
        "relations": ontology.get("relations", []),
        "metadata": {"generation_mode": mode},
        "warnings": _dedupe_text(warnings),
    }
    return result


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
