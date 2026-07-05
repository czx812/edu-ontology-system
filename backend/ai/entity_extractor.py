"""Entity extraction: text -> entity JSON through LLM."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.ai.llm_service import LLMService
from backend.ai.prompts import build_entity_prompt


class EntityExtractor:
    """Extract entities, attributes, and relations from education text with LLM."""

    def __init__(self, llm_service: Optional[LLMService] = None) -> None:
        self.llm_service = llm_service or LLMService()
        self.last_prompt = ""
        self.last_raw_result: Optional[Dict[str, Any]] = None

    def extract(self, text: str, use_llm: bool = True) -> Dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            return self._empty_result()
        if not use_llm:
            raise RuntimeError("Entity extraction requires LLM. Set use_llm=True.")
        if not self.llm_service.available:
            raise RuntimeError("LLM_API_KEY is not configured.")

        self.last_prompt = build_entity_prompt(clean_text)
        data = self.llm_service.chat_json(self.last_prompt)
        self.last_raw_result = data
        return self._normalize(data)

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "entities": self._dedupe_dicts(data.get("entities", []), "name"),
            "attributes": self._dedupe_dicts(
                data.get("attributes", []),
                ("entity", "name"),
            ),
            "relations": self._dedupe_dicts(
                data.get("relations", []),
                ("source", "target", "type"),
            ),
        }

    def _dedupe_dicts(
        self,
        items: Any,
        key: Union[str, Tuple[str, ...]],
    ) -> List[Dict[str, Any]]:
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

    def _empty_result(self) -> Dict[str, Any]:
        return {"entities": [], "attributes": [], "relations": []}
