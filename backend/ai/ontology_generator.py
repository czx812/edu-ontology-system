"""Ontology generation: text -> ontology JSON."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ai.entity_extractor import EntityExtractor
from ai.llm_service import LLMService


class OntologyGenerator:
    """Generate ontology JSON from extracted entities."""

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
        ontology = self._ontology_from_entities(entity_json)
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

    def _ontology_from_entities(self, entity_json: Dict[str, Any]) -> Dict[str, Any]:
        entities = entity_json.get("entities", [])
        attributes = entity_json.get("attributes", [])
        relations = entity_json.get("relations", [])

        classes = []
        for item in entities:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "")
            if not name:
                continue
            classes.append({
                "name": name,
                "label": item.get("label", name),
                "description": item.get("description", item.get("evidence", "")),
            })

        known_classes = {item.get("name") for item in classes if item.get("name")}
        properties = []
        for item in attributes:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "")
            if not name:
                continue
            domain = item.get("entity") or item.get("domain") or "EducationResource"
            if domain not in known_classes:
                classes.append({
                    "name": domain,
                    "label": domain,
                    "description": "Inferred class for extracted attributes.",
                })
                known_classes.add(domain)
            properties.append({
                "name": name,
                "label": item.get("label", name),
                "domain": domain,
                "range": item.get("data_type", item.get("range", "string")),
                "description": item.get("description", item.get("evidence", "")),
            })

        return {
            "classes": classes,
            "properties": properties,
            "relations": relations,
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
