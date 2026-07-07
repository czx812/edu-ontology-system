"""Entity extraction: clean_data/text -> entity JSON through LLM first."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.ai.llm_service import LLMService
from backend.ai.prompts import build_entity_prompt


CODE_RE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*\d{4,})\b")
SAFE_RE = re.compile(r"[^A-Za-z0-9_]+")


class EntityExtractor:
    """Extract concepts, attributes, and candidate relations from education data."""

    def __init__(self, llm_service: Optional[LLMService] = None) -> None:
        self.llm_service = llm_service or LLMService()
        self.last_prompt = ""
        self.last_raw_result: Optional[Dict[str, Any]] = None
        self.last_generation_mode = "llm"
        self.last_warnings: List[str] = []

    def extract(self, data: Any, use_llm: bool = True) -> Dict[str, Any]:
        if _is_empty(data):
            return self._empty_result("empty")

        self.last_prompt = build_entity_prompt(data)
        self.last_warnings = []

        if use_llm and self.llm_service.available:
            try:
                raw = self.llm_service.chat_json(self.last_prompt)
                self.last_generation_mode = "llm"
            except Exception as exc:
                self.last_warnings.append(f"LLM 实体抽取失败，已使用规则 fallback：{exc}")
                raw = self._rule_based_extract(data)
                self.last_generation_mode = "rule_fallback"
        else:
            self.last_warnings.append("LLM_API_KEY 未配置，已使用规则 fallback。")
            raw = self._rule_based_extract(data)
            self.last_generation_mode = "rule_fallback"

        self.last_raw_result = raw
        result = self._normalize(raw)
        result["metadata"] = {"generation_mode": self.last_generation_mode}
        if self.last_warnings:
            result["warnings"] = self.last_warnings[:]
        return result

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "entities": self._dedupe_dicts(data.get("entities", []), "name"),
            "attributes": self._dedupe_dicts(data.get("attributes", []), ("entity", "name")),
            "relations": self._dedupe_dicts(data.get("relations", []), ("source", "target", "type")),
        }

    def _rule_based_extract(self, data: Any) -> Dict[str, Any]:
        clean_data = _as_clean_data(data)
        records = clean_data.get("records", [])
        if not records:
            text = str(clean_data.get("clean_text") or clean_data.get("raw_text") or data)
            records = _records_from_text(text)

        entities: List[Dict[str, Any]] = []
        attributes: List[Dict[str, Any]] = []
        seen_entities: Set[str] = set()
        seen_attributes: Set[Tuple[str, str]] = set()

        for record in records:
            if not isinstance(record, dict):
                continue
            label = _first_text(record.get("cn_name"), record.get("item_name"), record.get("label"))
            name_source = _first_text(record.get("id"), record.get("name"), label)
            if not name_source or _is_noise(label or name_source):
                continue

            domain = _candidate_domain(record)
            if domain not in seen_entities:
                seen_entities.add(domain)
                entities.append({
                    "name": domain,
                    "label": _domain_label(domain),
                    "type": "class",
                    "description": f"{_domain_label(domain)}相关概念。",
                    "evidence": _evidence(record),
                    "low_confidence": domain == "EducationResource",
                })

            prop_name = _safe_property_name(name_source, label)
            marker = (domain, prop_name)
            if not prop_name or marker in seen_attributes:
                continue
            seen_attributes.add(marker)
            attributes.append({
                "entity": domain,
                "name": prop_name,
                "label": label or name_source,
                "type": "property",
                "data_type": _range_from_record(record),
                "description": _record_description(record),
                "evidence": _evidence(record),
                "low_confidence": domain == "EducationResource",
            })

        return {"entities": entities, "attributes": attributes, "relations": []}

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

    def _empty_result(self, mode: str = "llm") -> Dict[str, Any]:
        return {
            "entities": [],
            "attributes": [],
            "relations": [],
            "metadata": {"generation_mode": mode},
        }


def extract_entities(clean_data: Dict[str, Any]) -> Dict[str, Any]:
    """Workflow compatibility entry: C/D clean_data -> entity JSON."""
    return EntityExtractor().extract(clean_data, use_llm=True)


def _as_clean_data(data: Any) -> Dict[str, Any]:
    if isinstance(data, dict):
        return data
    return {"clean_text": str(data or "")}


def _is_empty(data: Any) -> bool:
    if data is None:
        return True
    if isinstance(data, str):
        return not data.strip()
    if isinstance(data, dict):
        return not any(data.get(key) for key in ("records", "tables", "clean_text", "raw_text", "text"))
    return False


def _records_from_text(text: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = " ".join(line.strip().split())
        if not line or _is_noise(line):
            continue
        match = CODE_RE.search(line)
        if not match:
            continue
        code = match.group(1)
        rest = line[match.end():].strip(" |:：")
        label = rest.split("|", 1)[0].strip() or code
        records.append({"id": code, "cn_name": label, "description": line, "evidence": line})
    return records


def _candidate_domain(record: Dict[str, Any]) -> str:
    text = " ".join(
        _first_text(record.get(key))
        for key in ("id", "source_table", "source_section", "item_name", "cn_name", "description")
    )
    code = _first_text(record.get("id")).upper()
    if code.startswith("JCXX") or any(word in text for word in ("学校", "校区", "班级", "年级")):
        if "校区" in text:
            return "Campus"
        if "班" in text:
            return "Class"
        if "年级" in text:
            return "Grade"
        return "School"
    if code.startswith("JCXS") or "学生" in text or "学籍" in text:
        if any(word in text for word in ("成绩", "考试", "课程成绩")):
            return "Score"
        if "奖励" in text:
            return "Reward"
        if "处分" in text:
            return "Punishment"
        if "毕业" in text:
            return "Graduation"
        return "Student"
    if code.startswith("JCJG") or any(word in text for word in ("教师", "教职工", "职务", "考核")):
        if "职务" in text:
            return "Position"
        if "考核" in text:
            return "Assessment"
        return "Staff"
    if code.startswith("JCBX") or any(word in text for word in ("经费", "建筑", "房间", "仪器", "图书")):
        if "建筑" in text:
            return "Building"
        if "房间" in text:
            return "Room"
        if "仪器" in text:
            return "Instrument"
        if "图书" in text:
            return "Book"
        if any(word in text for word in ("经费", "收入", "支出")):
            return "FinanceItem"
        return "Facility"
    if code.startswith("JCTB") or any(word in text for word in ("电话", "邮箱", "邮编", "单位", "专业", "课程")):
        if any(word in text for word in ("电话", "邮箱", "邮编", "通信", "地址")):
            return "ContactInfo"
        if "单位" in text:
            return "Organization"
        if "课程" in text:
            return "Course"
        if "专业" in text:
            return "Major"
        if any(word in text for word in ("姓名", "性别", "出生")):
            return "Person"
    return "EducationResource"


def _domain_label(domain: str) -> str:
    labels = {
        "EducationResource": "教育资源",
        "Person": "人员",
        "Student": "学生",
        "Teacher": "教师",
        "Staff": "教职工",
        "School": "学校",
        "Campus": "校区",
        "Class": "班级",
        "Grade": "年级",
        "Course": "课程",
        "Major": "专业",
        "Organization": "机构",
        "ContactInfo": "联系信息",
        "Score": "成绩",
        "Reward": "奖励",
        "Punishment": "处分",
        "Graduation": "毕业信息",
        "Position": "职务",
        "Assessment": "考核",
        "FinanceItem": "经费项目",
        "Building": "建筑物",
        "Room": "房间",
        "Facility": "设施",
        "Instrument": "仪器设备",
        "Book": "图书",
    }
    return labels.get(domain, domain)


def _safe_property_name(value: Any, label: str = "") -> str:
    text = _first_text(value)
    match = CODE_RE.search(text)
    if match:
        return match.group(1).lower()
    text = SAFE_RE.sub("_", text).strip("_").lower()
    if not text and label:
        text = SAFE_RE.sub("_", label).strip("_").lower()
    return text[:80]


def _range_from_record(record: Dict[str, Any]) -> str:
    text = " ".join(_first_text(record.get(key)) for key in ("cn_name", "item_name", "description", "data_type"))
    if any(word in text for word in ("日期", "出生日期", "入学年月", "建校年月", "出版日期", "评定日期")):
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


def _record_description(record: Dict[str, Any]) -> str:
    return "；".join(
        part
        for part in (
            _first_text(record.get("item_name")),
            _first_text(record.get("description")),
            _first_text(record.get("value_space")),
            _first_text(record.get("reference")),
        )
        if part
    )


def _evidence(record: Dict[str, Any]) -> str:
    return _first_text(
        record.get("evidence"),
        record.get("source_table"),
        record.get("source_section"),
        record.get("description"),
    )[:160]


def _is_noise(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return True
    if value in {"码", "号", "称", "位", "期", "箱", "女", "话"}:
        return True
    return any(
        word in value
        for word in (
            "目录",
            "前言",
            "规范性引用文件",
            "术语和定义",
            "中华人民共和国教育行业标准",
            "教育部发布",
            "--- Table",
        )
    )


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""
