"""Ontology generation: text -> ontology JSON."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ai.entity_extractor import EntityExtractor
from ai.llm_service import LLMService
from modules.ontology_builder import build_ontology
from modules.semantic_classifier import semantic_classify


class OntologyGenerator:
    """Generate ontology JSON through entity extraction and semantic classification."""

    def __init__(
        self,
        extractor: Optional[EntityExtractor] = None,
        llm_service: Optional[LLMService] = None,
    ) -> None:
        self.llm_service = llm_service or LLMService()
        self.extractor = extractor or EntityExtractor(self.llm_service)
        self.last_entity_json: Optional[Dict[str, Any]] = None
        self.last_semantic_model: Optional[Dict[str, Any]] = None
        self.last_ontology_prompt = ""
        self.last_raw_ontology: Optional[Dict[str, Any]] = None

    def generate(self, text: str, use_llm: bool = True) -> Dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            return self._empty_ontology()

        entity_json = self.extractor.extract(clean_text, use_llm=use_llm)
        self.last_entity_json = entity_json
        semantic_model = semantic_classify({"entity_json": entity_json, "clean_data": {}})
        self.last_semantic_model = semantic_model
        ontology = build_ontology(semantic_model)
        self.last_raw_ontology = ontology
        return self._normalize(ontology)

    def generate_with_steps(self, text: str, use_llm: bool = True) -> Dict[str, Any]:
        ontology_json = self.generate(text, use_llm=use_llm)
        entity_json = self.last_entity_json or {"entities": [], "attributes": [], "relations": []}
        return {
            "entity_prompt": self.extractor.last_prompt,
            "entity_json": entity_json,
            "semantic_model": self.last_semantic_model or {},
            "ontology_prompt": self.last_ontology_prompt,
            "ontology_json": ontology_json,
        }

    def _normalize(self, ontology: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "classes": self._normalize_classes(ontology.get("classes", [])),
            "properties": self._normalize_properties(ontology.get("properties", [])),
            "relations": self._dedupe(ontology.get("relations", []), ("source", "target", "type")),
        }

    def _normalize_classes(self, items: Any) -> List[Dict[str, Any]]:
        classes = self._dedupe(items, "name")
        return [
            {
                "name": item.get("name", ""),
                "label": item.get("label", item.get("name", "")),
                "description": item.get("description", ""),
            }
            for item in classes
            if item.get("name")
        ]

    def _normalize_properties(self, items: Any) -> List[Dict[str, Any]]:
        properties = self._dedupe(items, ("domain", "name"))
        return [
            {
                "name": item.get("name", ""),
                "label": item.get("label", item.get("name", "")),
                "domain": item.get("domain", ""),
                "range": item.get("range", "string"),
                "description": item.get("description", ""),
            }
            for item in properties
            if item.get("name")
        ]

    def _dedupe(self, items: Any, key: Union[str, Tuple[str, ...]]) -> List[Dict[str, Any]]:
        if not isinstance(items, list):
            return []

        seen: Set[Any] = set()
        result: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            marker = tuple(item.get(part, "") for part in key) if isinstance(key, tuple) else item.get(key, "")
            if not marker or marker in seen:
                continue
            seen.add(marker)
            result.append(item)
        return result

    def _empty_ontology(self) -> Dict[str, Any]:
        return {"classes": [], "properties": [], "relations": []}


def generate_ontology_json(text: str, use_llm: bool = True) -> str:
    """Convenience helper for callers that need a JSON string."""
    ontology = OntologyGenerator().generate(text, use_llm=use_llm)
    return json.dumps(ontology, ensure_ascii=False, indent=2)
