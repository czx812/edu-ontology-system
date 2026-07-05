"""Ontology generation: text -> ontology JSON through LLM."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ai.entity_extractor import EntityExtractor
from ai.llm_service import LLMService
from ai.prompts import build_ontology_prompt


class OntologyGenerator:
    """Run the B-layer LLM chain and generate final ontology JSON."""

    def __init__(
        self,
        extractor: Optional[EntityExtractor] = None,
        llm_service: Optional[LLMService] = None,
    ) -> None:
        self.llm_service = llm_service or LLMService()
        self.extractor = extractor or EntityExtractor(self.llm_service)
        self.last_entity_json: Optional[Dict[str, Any]] = None
        self.last_ontology_prompt = ""
        self.last_raw_ontology: Optional[Dict[str, Any]] = None

    def generate(self, text: str, use_llm: bool = True) -> Dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            return self._empty_ontology()
        if not use_llm:
            raise RuntimeError("Ontology generation requires LLM. Set use_llm=True.")
        if not self.llm_service.available:
            raise RuntimeError("LLM_API_KEY is not configured.")

        entity_json = self.extractor.extract(clean_text, use_llm=True)
        self.last_entity_json = entity_json
        self.last_ontology_prompt = build_ontology_prompt(clean_text, entity_json)

        ontology = self.llm_service.chat_json(self.last_ontology_prompt)
        self.last_raw_ontology = ontology
        return self._normalize(ontology)

    def generate_with_steps(self, text: str, use_llm: bool = True) -> Dict[str, Any]:
        ontology_json = self.generate(text, use_llm=use_llm)
        entity_json = self.last_entity_json or {
            "entities": [],
            "attributes": [],
            "relations": [],
        }
        return {
            "entity_prompt": self.extractor.last_prompt,
            "entity_json": entity_json,
            "ontology_prompt": self.last_ontology_prompt,
            "ontology_json": ontology_json,
        }

    def _normalize(self, ontology: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "classes": self._normalize_classes(ontology.get("classes", [])),
            "properties": self._normalize_properties(ontology.get("properties", [])),
            "relations": self._dedupe(
                ontology.get("relations", []),
                ("source", "target", "type"),
            ),
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
            marker = (
                tuple(item.get(part, "") for part in key)
                if isinstance(key, tuple)
                else item.get(key, "")
            )
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
