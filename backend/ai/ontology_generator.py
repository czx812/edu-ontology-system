"""Ontology generation: clean_data/text -> ontology JSON through two-stage LLM."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.ai.entity_extractor import EntityExtractor
from backend.ai.llm_service import LLMService
from backend.ai.prompts import build_global_relation_prompt, build_ontology_prompt


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
        self.last_relation_prompt = ""
        self.last_raw_ontology: Optional[Dict[str, Any]] = None
        self.last_generation_mode = "llm"
        self.last_warnings: List[str] = []

    def generate(self, data: Any, use_llm: bool = True) -> Dict[str, Any]:
        if _is_empty(data):
            return self._empty_ontology()

        self.last_warnings = []
        if use_llm and self.llm_service.available and _should_batch_records(data):
            return self._generate_batched(data)

        entity_json = self.extractor.extract(data, use_llm=use_llm)
        self.last_entity_json = entity_json
        self.last_warnings.extend(entity_json.get("warnings", []))

        if use_llm and self.llm_service.available:
            self.last_ontology_prompt = build_ontology_prompt(data, entity_json)
            try:
                ontology = self.llm_service.chat_json(self.last_ontology_prompt)
                self.last_generation_mode = "llm"
            except Exception as exc:
                self.last_warnings.append(f"LLM 本体生成失败，已使用规则 fallback：{exc}")
                ontology = self._rule_fallback(entity_json)
                self.last_generation_mode = "rule_fallback"
        else:
            self.last_warnings.append("LLM_API_KEY 未配置，已使用规则 fallback。")
            ontology = self._rule_fallback(entity_json)
            self.last_generation_mode = "rule_fallback"

        if entity_json.get("metadata", {}).get("generation_mode") == "rule_fallback":
            self.last_generation_mode = "rule_fallback"

        self.last_raw_ontology = ontology
        normalized = self._normalize(ontology)
        if use_llm and self.llm_service.available:
            normalized = self._add_global_relations(normalized)
        if not normalized["relations"]:
            self.last_warnings.append("当前大模型未识别出对象关系，OWL 中不会生成 owl:ObjectProperty。")
        return normalized

    def _generate_batched(self, data: Dict[str, Any]) -> Dict[str, Any]:
        records = data.get("records", [])
        batches = list(_record_batches(records, _batch_size()))
        merged_entity: Dict[str, Any] = {"entities": [], "attributes": [], "relations": []}
        merged_ontology: Dict[str, Any] = {"classes": [], "properties": [], "relations": []}
        fallback_batches = 0

        for index, batch in enumerate(batches, start=1):
            chunk_data = _chunk_data(data, batch, index, len(batches))
            entity_json = self.extractor.extract(chunk_data, use_llm=True)
            self.last_warnings.extend(entity_json.get("warnings", []))
            merged_entity = _merge_entity_json(merged_entity, entity_json)

            self.last_ontology_prompt = build_ontology_prompt(chunk_data, entity_json)
            try:
                ontology = self.llm_service.chat_json(self.last_ontology_prompt)
            except Exception as exc:
                fallback_batches += 1
                self.last_warnings.append(
                    f"LLM batch {index}/{len(batches)} ontology generation failed; used rule fallback: {exc}"
                )
                ontology = self._rule_fallback(entity_json)

            merged_ontology = _merge_ontology_json(merged_ontology, self._normalize(ontology))

        self.last_entity_json = merged_entity
        self.last_raw_ontology = merged_ontology
        self.last_generation_mode = "llm_batched" if fallback_batches == 0 else "mixed_fallback"
        normalized = self._normalize(merged_ontology)
        normalized = self._add_global_relations(normalized)
        self.last_warnings.append(
            f"已分 {len(batches)} 批完整处理 {len(records)} 条 records，每批约 {_batch_size()} 条。"
        )
        if not normalized["relations"]:
            self.last_warnings.append("当前大模型未识别出对象关系，OWL 中不会生成 owl:ObjectProperty。")
        return normalized

    def _add_global_relations(self, ontology: Dict[str, Any]) -> Dict[str, Any]:
        if os.getenv("LLM_GLOBAL_RELATIONS", "1").lower() in {"0", "false", "no", "off"}:
            return ontology
        if len(ontology.get("classes", [])) < 2:
            return ontology

        self.last_relation_prompt = build_global_relation_prompt(
            ontology,
            self.last_entity_json or {"entities": [], "attributes": [], "relations": []},
        )
        try:
            relation_result = self.llm_service.chat_json(self.last_relation_prompt)
        except Exception as exc:
            self.last_warnings.append(f"Global relation inference failed; kept existing relations: {exc}")
            return ontology

        inferred = {
            "classes": [],
            "properties": [],
            "relations": relation_result.get("relations", []),
        }
        merged = _merge_ontology_json(ontology, self._normalize(inferred))
        normalized = self._normalize(merged)
        added = len(normalized.get("relations", [])) - len(ontology.get("relations", []))
        if added > 0:
            self.last_warnings.append(f"Global relation inference added {added} cross-table relations.")
        return normalized

    def generate_with_steps(self, data: Any, use_llm: bool = True) -> Dict[str, Any]:
        ontology_json = self.generate(data, use_llm=use_llm)
        entity_json = self.last_entity_json or {"entities": [], "attributes": [], "relations": []}
        return {
            "entity_prompt": self.extractor.last_prompt,
            "entity_json": entity_json,
            "ontology_prompt": self.last_ontology_prompt,
            "relation_prompt": self.last_relation_prompt,
            "ontology_json": ontology_json,
            "generation_mode": self.last_generation_mode,
            "warnings": self.last_warnings,
        }

    def _normalize(self, ontology: Dict[str, Any]) -> Dict[str, Any]:
        classes = self._normalize_classes(ontology.get("classes", []))
        properties = self._normalize_properties(ontology.get("properties", []))
        relations = self._normalize_relations(ontology.get("relations", []))
        class_names = {item["name"] for item in classes}

        for prop in properties:
            domain = prop.get("domain") or "EducationResource"
            if domain not in class_names:
                classes.append({
                    "name": domain,
                    "label": domain,
                    "description": "由属性 domain 引用补充的类。",
                    "low_confidence": True,
                })
                class_names.add(domain)

        for relation in relations:
            for endpoint in (relation.get("source"), relation.get("target")):
                if endpoint and endpoint not in class_names:
                    classes.append({
                        "name": endpoint,
                        "label": endpoint,
                        "description": "由关系端点引用补充的类。",
                        "low_confidence": True,
                    })
                    class_names.add(endpoint)

        return {"classes": classes, "properties": properties, "relations": relations}

    def _normalize_classes(self, items: Any) -> List[Dict[str, Any]]:
        classes = self._dedupe(items, "name")
        result: List[Dict[str, Any]] = []
        for item in classes:
            name = _safe_class_name(item.get("name") or item.get("label"))
            label = str(item.get("label") or name).strip()
            if not name or _is_noise(label):
                continue
            normalized = {
                "name": name,
                "label": label,
                "description": str(item.get("description") or "").strip(),
            }
            for optional in ("parent", "evidence", "low_confidence"):
                if item.get(optional):
                    normalized[optional] = item[optional]
            if not normalized.get("evidence"):
                normalized["low_confidence"] = True
            result.append(normalized)
        return result

    def _normalize_properties(self, items: Any) -> List[Dict[str, Any]]:
        properties = self._dedupe(items, ("domain", "name"))
        result: List[Dict[str, Any]] = []
        for item in properties:
            name = _safe_property_name(item.get("name") or item.get("label"))
            label = str(item.get("label") or name).strip()
            domain = _safe_class_name(item.get("domain") or "EducationResource")
            if not name or _is_noise(label):
                continue
            normalized = {
                "name": name,
                "label": label,
                "domain": domain or "EducationResource",
                "range": _normalize_range(item.get("range") or item.get("data_type"), label, name, item.get("description")),
                "description": str(item.get("description") or "").strip(),
            }
            for optional in ("evidence", "low_confidence"):
                if item.get(optional):
                    normalized[optional] = item[optional]
            if not normalized.get("evidence"):
                normalized["low_confidence"] = True
            result.append(normalized)
        return result

    def _normalize_relations(self, items: Any) -> List[Dict[str, Any]]:
        relations = self._dedupe(items, ("source", "target", "type"))
        result: List[Dict[str, Any]] = []
        for item in relations:
            source = _safe_class_name(item.get("source") or item.get("subject"))
            target = _safe_class_name(item.get("target") or item.get("object"))
            rel_type = _safe_property_name(item.get("type") or item.get("predicate") or item.get("relation"))
            if not source or not target or not rel_type:
                continue
            relation = {
                "source": source,
                "target": target,
                "type": rel_type,
                "label": str(item.get("label") or rel_type).strip(),
                "description": str(item.get("description") or item.get("reason") or "").strip(),
            }
            for optional in ("evidence", "reason", "low_confidence"):
                if item.get(optional):
                    relation[optional] = item[optional]
            if not relation.get("evidence") and not relation.get("reason"):
                relation["low_confidence"] = True
            result.append(relation)
        return result

    def _rule_fallback(self, entity_json: Dict[str, Any]) -> Dict[str, Any]:
        classes = []
        properties = []
        for entity in entity_json.get("entities", []):
            if not isinstance(entity, dict):
                continue
            classes.append({
                "name": entity.get("name"),
                "label": entity.get("label"),
                "description": entity.get("description", ""),
                "parent": entity.get("parent", ""),
                "evidence": entity.get("evidence", ""),
                "low_confidence": entity.get("low_confidence", True),
            })
        for attr in entity_json.get("attributes", []):
            if not isinstance(attr, dict):
                continue
            properties.append({
                "name": attr.get("name"),
                "label": attr.get("label"),
                "domain": attr.get("entity") or attr.get("domain") or "EducationResource",
                "range": attr.get("data_type") or attr.get("range") or "string",
                "description": attr.get("description", ""),
                "evidence": attr.get("evidence", ""),
                "low_confidence": attr.get("low_confidence", True),
            })
        return {
            "classes": classes,
            "properties": properties,
            "relations": entity_json.get("relations", []),
        }

    def _dedupe(self, items: Any, key: Union[str, Tuple[str, ...]]) -> List[Dict[str, Any]]:
        if not isinstance(items, list):
            return []

        seen: Set[Any] = set()
        result: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            marker = (
                tuple(str(item.get(part, "")).lower() for part in key)
                if isinstance(key, tuple)
                else str(item.get(key, "")).lower()
            )
            if not marker or marker in seen:
                continue
            seen.add(marker)
            result.append(item)
        return result

    def _empty_ontology(self) -> Dict[str, Any]:
        return {"classes": [], "properties": [], "relations": []}


def _batch_size() -> int:
    try:
        return max(1, int(os.getenv("LLM_BATCH_RECORDS", os.getenv("LLM_MAX_PROMPT_RECORDS", "60"))))
    except ValueError:
        return 60


def _should_batch_records(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    records = data.get("records")
    return isinstance(records, list) and len(records) > _batch_size()


def _record_batches(records: List[Any], size: int) -> List[List[Any]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def _chunk_data(data: Dict[str, Any], records: List[Any], index: int, total: int) -> Dict[str, Any]:
    chunk = dict(data)
    chunk["records"] = records
    chunk["records_count"] = len(records)
    chunk["batch"] = {
        "index": index,
        "total": total,
        "note": "This is one complete batch of the source records. Do not infer from omitted batches.",
    }
    chunk.pop("tables", None)
    if chunk.get("raw_text"):
        chunk["raw_text"] = str(chunk["raw_text"])[:2000]
    if chunk.get("clean_text"):
        chunk["clean_text"] = str(chunk["clean_text"])[:2000]
    return chunk


def _merge_entity_json(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "entities": _dedupe_items([*left.get("entities", []), *right.get("entities", [])], "name"),
        "attributes": _dedupe_items([*left.get("attributes", []), *right.get("attributes", [])], ("entity", "name")),
        "relations": _dedupe_items([*left.get("relations", []), *right.get("relations", [])], ("source", "target", "type")),
        "metadata": {"generation_mode": "llm_batched"},
    }


def _merge_ontology_json(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "classes": _dedupe_items([*left.get("classes", []), *right.get("classes", [])], "name"),
        "properties": _dedupe_items([*left.get("properties", []), *right.get("properties", [])], ("domain", "name")),
        "relations": _dedupe_items([*left.get("relations", []), *right.get("relations", [])], ("source", "target", "type")),
    }


def _dedupe_items(items: List[Any], key: Union[str, Tuple[str, ...]]) -> List[Dict[str, Any]]:
    seen: Set[Any] = set()
    result: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        marker = (
            tuple(str(item.get(part, "")).lower() for part in key)
            if isinstance(key, tuple)
            else str(item.get(key, "")).lower()
        )
        if not marker or marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def generate_ontology_json(data: Any, use_llm: bool = True) -> str:
    """Convenience helper for callers that need a JSON string."""
    ontology = OntologyGenerator().generate(data, use_llm=use_llm)
    return json.dumps(ontology, ensure_ascii=False, indent=2)


def _is_empty(data: Any) -> bool:
    if data is None:
        return True
    if isinstance(data, str):
        return not data.strip()
    if isinstance(data, dict):
        return not any(data.get(key) for key in ("records", "tables", "clean_text", "raw_text", "text"))
    return False


def _safe_class_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re_sub_identifier(text)
    if not text:
        return ""
    if "_" in text:
        return "".join(part[:1].upper() + part[1:] for part in text.split("_") if part)
    return text[:1].upper() + text[1:]


def _safe_property_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re_search_code(text)
    if match:
        return match.lower()
    text = re_sub_identifier(text).lower()
    if text in {"ma", "hao", "cheng", "wei", "qi", "xiang", "nv", "hua"}:
        return ""
    return text[:80]


def _normalize_range(value: Any, label: str = "", name: str = "", description: Any = "") -> str:
    text = str(value or "").strip().lower()
    if text in {"integer", "int"}:
        return "integer"
    if text in {"decimal", "float", "number"}:
        return "decimal"
    if text in {"boolean", "bool"}:
        return "boolean"
    if text in {"date", "time", "string"}:
        return text
    return infer_range(label, name, str(description or ""))


def infer_range(label: str, name: str = "", description: str = "") -> str:
    text = f"{label} {name} {description}"
    if any(word in text for word in ("日期", "日", "出生日期", "入学年月", "建校年月", "出版日期", "评定日期")):
        return "date"
    if "时间" in text:
        return "time"
    if any(word in text for word in ("人数", "人口", "数量", "层数", "页数", "个数", "时数")):
        return "integer"
    if any(word in text for word in ("金额", "收入", "支出", "费用", "价格", "工资", "拨款", "债务", "经费", "面积", "单价")):
        return "decimal"
    if any(word in text for word in ("是否", "标志", "正常", "不正常")):
        return "boolean"
    return "string"


def re_search_code(text: str) -> str:
    import re

    match = re.search(r"\b([A-Z]{2,}[A-Z0-9]*\d{4,})\b", text, flags=re.I)
    return match.group(1) if match else ""


def re_sub_identifier(text: str) -> str:
    import re

    text = re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")
    return re.sub(r"_+", "_", text)


def _is_noise(label: str) -> bool:
    text = str(label or "").strip()
    if not text or text in {"码", "号", "称", "位", "期", "箱", "女", "话"}:
        return True
    if len(text) == 1:
        return True
    return any(
        word in text
        for word in (
            "目录",
            "前言",
            "规范性引用文件",
            "术语和定义",
            "中华人民共和国教育行业标准",
            "教育部发布",
            "--- Table",
            "编号",
            "中文简称",
            "数据项名",
            "解释/举例",
            "值空间",
            "引用编号",
        )
    )
