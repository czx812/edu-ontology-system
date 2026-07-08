from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List


RELATION_WORDS = (
    "关联",
    "引用",
    "属于",
    "包含",
    "对应",
    "关系",
    "上级",
    "下级",
    "parent",
    "child",
    "reference",
    "belongs",
)


def analyze_document_structure(clean_data: dict, raw_text: str = "") -> dict:
    records = clean_data.get("records", []) if isinstance(clean_data, dict) else []
    tables = clean_data.get("tables", []) if isinstance(clean_data, dict) else []
    text = str(raw_text or clean_data.get("clean_text") or clean_data.get("raw_text") or "")

    sections = _section_hierarchy(text, records)
    table_groups = _table_groups(tables, records)
    record_groups = _record_groups(records)
    relation_clues = _relation_clues(records, text)
    detected_groups = _detected_groups(records, relation_clues)

    return {
        "document_title": _document_title(text, records),
        "document_type": _document_type(text),
        "total_records": len(records),
        "sections": sections[:60],
        "section_hierarchy": sections,
        "table_groups": table_groups,
        "record_groups": record_groups,
        "detected_groups": detected_groups[:20],
        "sample_records": _global_samples(detected_groups, limit=60),
        "relation_clues": relation_clues,
        "detected_patterns": _detected_patterns(records, relation_clues),
    }


def _document_title(text: str, records: List[Any]) -> str:
    for line in text.splitlines():
        line = " ".join(line.strip().split())
        if len(line) >= 4 and not re.match(r"^\d+(\.\d+)*\s+", line):
            return line[:120]
    for record in records:
        if isinstance(record, dict):
            title = str(record.get("source_section") or record.get("source_table") or "").strip()
            if title:
                return title[:120]
    return "Education Ontology Document"


def _document_type(text: str) -> str:
    if "标准" in text or "规范" in text:
        return "standard"
    if "指南" in text:
        return "guide"
    return "education_document"


def _section_hierarchy(text: str, records: List[Any]) -> List[dict]:
    sections: List[dict] = []
    seen = set()
    for line in text.splitlines():
        line = " ".join(line.strip().split())
        if not line:
            continue
        match = re.match(r"^(\d+(?:\.\d+)*)\s+(.{2,120})$", line)
        if match:
            section_id = match.group(1)
            title = match.group(2)
            key = (section_id, title)
            if key not in seen:
                seen.add(key)
                sections.append({"id": section_id, "title": title, "level": section_id.count(".") + 1})
    if sections:
        return sections[:200]

    for record in records:
        if not isinstance(record, dict):
            continue
        title = str(record.get("source_section") or "").strip()
        if title and title not in seen:
            seen.add(title)
            sections.append({"id": str(len(sections) + 1), "title": title, "level": 1})
    return sections[:200]


def _table_groups(tables: List[Any], records: List[Any]) -> List[dict]:
    groups = []
    for index, table in enumerate(tables if isinstance(tables, list) else [], start=1):
        if isinstance(table, dict):
            title = str(table.get("title") or table.get("name") or f"Table {index}")
            rows = table.get("rows") if isinstance(table.get("rows"), list) else []
        else:
            title = f"Table {index}"
            rows = table if isinstance(table, list) else []
        groups.append({"table_id": f"table_{index}", "title": title, "record_count": len(rows)})
    if groups:
        return groups

    counts: Dict[str, int] = defaultdict(int)
    for record in records:
        if isinstance(record, dict):
            key = str(record.get("source_table") or record.get("source_section") or "Ungrouped")
            counts[key] += 1
    return [{"table_id": _safe_id(title), "title": title, "record_count": count} for title, count in counts.items()]


def _record_groups(records: List[Any]) -> List[dict]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        title = str(record.get("source_table") or record.get("source_section") or "Ungrouped").strip() or "Ungrouped"
        grouped[title].append(_record_id(record, len(grouped[title])))
    return [
        {"group_id": _safe_id(title), "group_title": title, "record_count": len(ids), "record_ids": ids}
        for title, ids in grouped.items()
    ]


def _detected_groups(records: List[Any], relation_clues: List[dict]) -> List[dict]:
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        title = str(record.get("source_table") or record.get("source_section") or _code_prefix(record) or "Ungrouped").strip() or "Ungrouped"
        buckets[title].append(record)

    groups = []
    for title, items in sorted(buckets.items(), key=lambda item: len(item[1]), reverse=True)[:20]:
        record_ids = {_record_id(record, index) for index, record in enumerate(items)}
        group_clues = [
            clue for clue in relation_clues
            if not clue.get("source") or clue.get("source") == title or str(clue.get("record_id") or "") in record_ids
        ][:10]
        groups.append({
            "group_id": _safe_id(title),
            "group_title": title,
            "record_count": len(items),
            "representative_fields": _representative_fields(items),
            "field_patterns": _field_patterns(items),
            "possible_entities": _possible_entities(items),
            "relation_clues": group_clues,
            "sample_records": [_compact_record(record, index) for index, record in enumerate(items[:3])],
        })
    return groups


def _relation_clues(records: List[Any], text: str) -> List[dict]:
    clues: List[dict] = []
    for index, record in enumerate(records if isinstance(records, list) else []):
        if not isinstance(record, dict):
            continue
        blob = " ".join(str(record.get(k) or "") for k in ("id", "code", "cn_name", "item_name", "description", "reference", "reference_id", "source_section"))
        if any(word.lower() in blob.lower() for word in RELATION_WORDS):
            clues.append({
                "record_id": _record_id(record, index),
                "text": blob[:300],
                "source": str(record.get("source_table") or record.get("source_section") or ""),
            })
    for line in text.splitlines():
        compact = " ".join(line.strip().split())
        if compact and any(word.lower() in compact.lower() for word in RELATION_WORDS):
            clues.append({"record_id": "", "text": compact[:300], "source": "raw_text"})
        if len(clues) >= 500:
            break
    return clues[:500]


def _detected_patterns(records: List[Any], relation_clues: List[dict]) -> List[str]:
    patterns = []
    if relation_clues:
        patterns.append("relation_clues")
    if any(isinstance(r, dict) and (r.get("reference") or r.get("reference_id")) for r in records if isinstance(records, list)):
        patterns.append("reference_fields")
    if any(isinstance(r, dict) and r.get("source_table") for r in records if isinstance(records, list)):
        patterns.append("table_scoped_records")
    if any(isinstance(r, dict) and re.search(r"[A-Za-z]+\d+", str(r.get("id") or r.get("code") or "")) for r in records if isinstance(records, list)):
        patterns.append("coded_records")
    return patterns


def _representative_fields(records: List[dict]) -> List[str]:
    counter = Counter()
    for record in records:
        for key in ("id", "code", "item_name", "cn_name", "data_type", "length", "constraint", "value_space", "description", "reference"):
            if str(record.get(key) or "").strip():
                counter[key] += 1
    return [key for key, _ in counter.most_common(5)]


def _field_patterns(records: List[dict]) -> List[str]:
    patterns = []
    if any(str(item.get("id") or item.get("code") or "").strip() for item in records):
        patterns.append("coded_records")
    if any(str(item.get("reference") or item.get("reference_id") or "").strip() for item in records):
        patterns.append("reference_fields")
    if any(str(item.get("data_type") or "").strip() for item in records):
        patterns.append("typed_fields")
    return patterns


def _possible_entities(records: List[dict]) -> List[str]:
    counter = Counter()
    for record in records:
        for domain in record.get("candidate_domains", []) if isinstance(record.get("candidate_domains"), list) else []:
            counter[str(domain)] += 1
    return [name for name, _ in counter.most_common(6)] or ["EducationResource"]


def _compact_record(record: dict, index: int) -> dict:
    rid = _record_id(record, index)
    return {
        "record_id": rid,
        "code": str(record.get("code") or record.get("id") or "")[:80],
        "name": str(record.get("cn_name") or record.get("item_name") or record.get("name") or rid)[:120],
        "data_type": str(record.get("data_type") or record.get("type") or "")[:60],
        "description": str(record.get("description") or "")[:240],
        "reference": str(record.get("reference") or record.get("reference_id") or "")[:80],
    }


def _global_samples(groups: List[dict], limit: int = 60) -> List[dict]:
    samples = []
    for group in groups:
        for record in group.get("sample_records", [])[:3]:
            samples.append(record)
            if len(samples) >= limit:
                return samples
    return samples


def _record_id(record: dict, index: int) -> str:
    return str(record.get("id") or record.get("code") or record.get("record_id") or record.get("name") or f"record_{index + 1}")


def _code_prefix(record: dict) -> str:
    code = str(record.get("id") or record.get("code") or "").strip()
    match = re.match(r"([A-Za-z]+)", code)
    return match.group(1) if match else ""


def _safe_id(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "").strip()).strip("_")
    return text[:80] or "group"
