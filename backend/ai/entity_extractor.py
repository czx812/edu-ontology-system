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
    """Extract concepts, properties, and relations from education text."""

    def __init__(self, llm_service: Optional[LLMService] = None) -> None:
        self.llm_service = llm_service or LLMService()
        self.last_prompt = ""
        self.last_raw_result: Optional[Dict[str, Any]] = None

    def extract(self, text: str, use_llm: bool = True) -> Dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            return self._empty_result()

        self.last_prompt = build_entity_prompt(clean_text)
        if use_llm and self.llm_service.available:
            try:
                data = self.llm_service.chat_json(self.last_prompt)
            except ValueError:
                data = self._rule_based_extract(clean_text)
        else:
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

            domain = self._infer_domain(label)
            if domain not in seen_entities:
                seen_entities.add(domain)
                entities.append({
                    "name": domain,
                    "label": self._domain_label(domain),
                    "type": "class",
                    "semantic_type": "class",
                    "description": f"{self._domain_label(domain)}概念",
                    "evidence": evidence,
                })

            marker = (domain, code)
            if marker not in seen_attributes:
                seen_attributes.add(marker)
                attributes.append({
                    "entity": domain,
                    "name": code,
                    "label": label,
                    "type": "property",
                    "semantic_type": "property",
                    "data_type": "string",
                    "description": f"{self._domain_label(domain)}的{label}",
                    "evidence": evidence,
                })

            if len(attributes) >= MAX_FALLBACK_ATTRIBUTES:
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

    def _infer_domain(self, label: str) -> str:
        if "学生" in label:
            return "Student"
        if "学校" in label or "院校" in label:
            return "School"
        if "联系" in label or "电话" in label or "邮箱" in label or "邮编" in label:
            return "ContactInfo"
        if "教师" in label:
            return "Teacher"
        if "课程" in label:
            return "Course"
        return "EducationResource"

    def _domain_label(self, domain: str) -> str:
        return {
            "Student": "学生",
            "School": "学校",
            "ContactInfo": "联系信息",
            "Teacher": "教师",
            "Course": "课程",
            "EducationResource": "教育资源",
        }.get(domain, domain)

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "entities": self._dedupe_dicts(data.get("entities", []), "name"),
            "attributes": self._dedupe_dicts(data.get("attributes", []), ("entity", "name")),
            "relations": self._dedupe_dicts(data.get("relations", []), ("source", "target", "type")),
        }

    def _dedupe_dicts(self, items: Any, key: Union[str, Tuple[str, ...]]) -> List[Dict[str, Any]]:
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

    def _empty_result(self) -> Dict[str, Any]:
        return {"entities": [], "attributes": [], "relations": []}


def extract_entities(clean_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract entity JSON from normalized clean_data."""
    records = clean_data.get("records", []) if isinstance(clean_data, dict) else []
    if records:
        return _records_to_entity_json(records)

    text = ""
    if isinstance(clean_data, dict):
        text = str(clean_data.get("clean_text") or clean_data.get("raw_text") or "")
    return EntityExtractor().extract(text, use_llm=True)


def _records_to_entity_json(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    entities: List[Dict[str, Any]] = []
    attributes: List[Dict[str, Any]] = []
    seen_entities = set()
    seen_attributes = set()

    for record in records:
        if not isinstance(record, dict):
            continue
        label_text = str(record.get("cn_name") or record.get("item_name") or "")
        domain = _infer_domain_from_text(" ".join([
            str(record.get("source_table") or ""),
            str(record.get("item_name") or ""),
            label_text,
            str(record.get("description") or ""),
        ]))
        if domain not in seen_entities:
            seen_entities.add(domain)
            entities.append({
                "name": domain,
                "label": _domain_label(domain),
                "type": "class",
                "semantic_type": "class",
                "description": "Inferred concept domain.",
                "evidence": str(record.get("source_table") or ""),
            })

        name = str(record.get("id") or record.get("item_name") or label_text).strip()
        if not name:
            continue
        marker = (domain, name)
        if marker in seen_attributes:
            continue
        seen_attributes.add(marker)
        attributes.append({
            "entity": domain,
            "name": name,
            "label": label_text or name,
            "type": "property",
            "semantic_type": "property",
            "data_type": record.get("data_type", "string") or "string",
            "description": str(record.get("description") or record.get("value_space") or ""),
            "evidence": str(record.get("source_table") or ""),
        })

    return {"entities": entities, "attributes": attributes, "relations": []}


def _infer_domain_from_text(text: str) -> str:
    if "学生" in text:
        return "Student"
    if "学校" in text or "院校" in text:
        return "School"
    if "联系" in text or "电话" in text or "邮箱" in text or "邮编" in text:
        return "ContactInfo"
    if "教师" in text:
        return "Teacher"
    if "课程" in text:
        return "Course"
    return "EducationResource"


def _domain_label(domain: str) -> str:
    return {
        "Student": "学生",
        "School": "学校",
        "ContactInfo": "联系信息",
        "Teacher": "教师",
        "Course": "课程",
        "EducationResource": "教育资源",
    }.get(domain, domain)
