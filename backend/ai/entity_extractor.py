"""Entity extraction: text -> entity JSON through LLM with rule fallback."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ai.llm_service import LLMService
from ai.prompts import build_entity_prompt


CODE_RE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*\d{4,})\b")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
MAX_FALLBACK_ENTITIES = 300
MAX_FALLBACK_ATTRIBUTES = 500


class EntityExtractor:
    """Extract entities, attributes, and relations from education text."""

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
        try:
            data = self.llm_service.chat_json(self.last_prompt)
        except ValueError:
            data = self._rule_based_extract(clean_text)

        self.last_raw_result = data
        return self._normalize(data)

    def _rule_based_extract(self, text: str) -> Dict[str, Any]:
        entities: List[Dict[str, Any]] = []
        attributes: List[Dict[str, Any]] = []
        seen_entities: Set[str] = set()
        seen_attributes: Set[Tuple[str, str]] = set()

        for line in text.splitlines():
            line = " ".join(line.strip().split())
            if not line:
                continue

            row = [cell.strip() for cell in line.split("|")]
            code = ""
            label = ""
            evidence = line[:120]

            if len(row) >= 2 and CODE_RE.fullmatch(row[0]):
                code = row[0]
                label = self._clean_label(row[1])
            else:
                match = CODE_RE.search(line)
                if match:
                    code = match.group(1)
                    label = self._label_after_code(line[match.end() :])

            if not code or not label:
                continue

            entity_type = "table" if code.startswith("JCTB") else "field"
            if code not in seen_entities:
                seen_entities.add(code)
                entities.append(
                    {
                        "name": code,
                        "label": label,
                        "type": entity_type,
                        "description": f"{label}（{code}）",
                        "evidence": evidence,
                    }
                )

            for attr_name, attr_label in (("code", "编号"), ("label", "名称")):
                marker = (code, attr_name)
                if marker in seen_attributes:
                    continue
                seen_attributes.add(marker)
                attributes.append(
                    {
                        "entity": code,
                        "name": attr_name,
                        "label": attr_label,
                        "data_type": "string",
                        "description": f"{label}的{attr_label}",
                        "evidence": evidence,
                    }
                )

            if len(entities) >= MAX_FALLBACK_ENTITIES:
                break

        return {
            "entities": entities[:MAX_FALLBACK_ENTITIES],
            "attributes": attributes[:MAX_FALLBACK_ATTRIBUTES],
            "relations": [],
        }

    def _label_after_code(self, text: str) -> str:
        text = text.strip(" |:：\t")
        if not text:
            return ""
        parts = [part for part in re.split(r"\s+|\|", text) if part]
        for part in parts:
            label = self._clean_label(part)
            if label and CHINESE_RE.search(label):
                return label
        for part in parts:
            label = self._clean_label(part)
            if label:
                return label
        return ""

    def _clean_label(self, value: str) -> str:
        label = str(value or "").strip()
        label = re.sub(r"^[：:|\s]+|[：:|\s]+$", "", label)
        label = re.sub(r"\s+", "", label)
        if not label or CODE_RE.fullmatch(label):
            return ""
        if not CHINESE_RE.search(label) and len(label) > 30:
            return ""
        return label[:40]

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

