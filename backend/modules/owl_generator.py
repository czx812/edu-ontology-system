from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

try:
    from config import settings
except ModuleNotFoundError:
    from backend.config import settings


ONTOLOGY_BASE_URI = "http://example.org/edu-ontology#"
ONTOLOGY_DOC_URI = ONTOLOGY_BASE_URI.rstrip("#")
XSD_URI = "http://www.w3.org/2001/XMLSchema#"
XSD_RANGES = {
    "string": f"{XSD_URI}string",
    "integer": f"{XSD_URI}integer",
    "int": f"{XSD_URI}integer",
    "decimal": f"{XSD_URI}decimal",
    "float": f"{XSD_URI}decimal",
    "number": f"{XSD_URI}decimal",
    "boolean": f"{XSD_URI}boolean",
    "bool": f"{XSD_URI}boolean",
    "date": f"{XSD_URI}date",
    "time": f"{XSD_URI}time",
    "datetime": f"{XSD_URI}dateTime",
}


def infer_xsd_range(label: str = "", name: str = "", description: str = "") -> str:
    text = f"{label} {name} {description}".lower()
    if any(word in text for word in ("date", "日期", "年月")):
        return XSD_RANGES["date"]
    if any(word in text for word in ("time", "时间")):
        return XSD_RANGES["time"]
    if any(word in text for word in ("int", "integer", "人数", "数量", "个数")):
        return XSD_RANGES["integer"]
    if any(word in text for word in ("decimal", "float", "number", "金额", "面积")):
        return XSD_RANGES["decimal"]
    if any(word in text for word in ("bool", "boolean", "是否", "标志")):
        return XSD_RANGES["boolean"]
    return XSD_RANGES["string"]


def _safe_name(name: object, default: str = "Unnamed") -> str:
    text = str(name or "").strip()
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    return text or default


def _resource(name: object) -> str:
    return f"{ONTOLOGY_BASE_URI}{escape(_safe_name(name))}"


def _xsd_range(prop: dict) -> str:
    value = str(prop.get("range") or "string").strip().lower()
    if value in XSD_RANGES:
        return XSD_RANGES[value]
    return infer_xsd_range(str(prop.get("label") or ""), str(prop.get("id") or prop.get("name") or ""), str(prop.get("description") or ""))


def generate_owl(ontology: dict, export_dir: Optional[str] = None) -> str:
    """Generate RDF/XML OWL from ontology JSON."""
    ontology = ontology if isinstance(ontology, dict) else {}
    classes = ontology.get("classes", []) or []
    datatype_properties = ontology.get("datatype_properties") or ontology.get("properties") or []
    object_properties = ontology.get("object_properties") or []
    relations = ontology.get("relations") or []
    class_hierarchy = ontology.get("class_hierarchy") or []
    if not datatype_properties:
        raise RuntimeError("ONTOLOGY_VALIDATION_FAILED: datatype_properties=0，停止正常 OWL 导出。")

    object_properties = [*object_properties, *_object_properties_from_relations(relations)]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(export_dir) if export_dir else settings.EXPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"ontology_{timestamp}.owl"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<rdf:RDF",
        '  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
        '  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"',
        '  xmlns:owl="http://www.w3.org/2002/07/owl#"',
        '  xmlns:xsd="http://www.w3.org/2001/XMLSchema#"',
        f'  xmlns:edu="{escape(ONTOLOGY_BASE_URI)}">',
        "",
        f'  <owl:Ontology rdf:about="{escape(ONTOLOGY_DOC_URI)}">',
        * _ontology_metadata_lines(ontology),
        '  </owl:Ontology>',
        "",
        f'  <owl:AnnotationProperty rdf:about="{_resource("sourceRecordIds")}"/>',
        f'  <owl:AnnotationProperty rdf:about="{_resource("sourceDoc")}"/>',
        f'  <owl:AnnotationProperty rdf:about="{_resource("sourceTable")}"/>',
        f'  <owl:AnnotationProperty rdf:about="{_resource("sourceFile")}"/>',
        f'  <owl:AnnotationProperty rdf:about="{_resource("sourceFilename")}"/>',
        f'  <owl:AnnotationProperty rdf:about="{_resource("sourcePage")}"/>',
        f'  <owl:AnnotationProperty rdf:about="{_resource("sourceRow")}"/>',
        f'  <owl:AnnotationProperty rdf:about="{_resource("sourcesJson")}"/>',
        "",
    ]

    hierarchy_map = _hierarchy_map(class_hierarchy)
    for cls in classes:
        if not isinstance(cls, dict):
            continue
        name = _safe_name(cls.get("id") or cls.get("name") or cls.get("label"), "Class")
        label = str(cls.get("label") or name)
        description = str(cls.get("description") or "")
        parents = hierarchy_map.get(name, [])
        if cls.get("parent"):
            parents.append(_safe_name(cls.get("parent"), ""))

        lines.append(f'  <owl:Class rdf:about="{_resource(name)}">')
        lines.append(f"    <rdfs:label>{escape(label)}</rdfs:label>")
        if description:
            lines.append(f"    <rdfs:comment>{escape(description)}</rdfs:comment>")
        _append_source_comment(lines, cls)
        for parent in sorted(set(p for p in parents if p and p != name)):
            lines.append(f'    <rdfs:subClassOf rdf:resource="{_resource(parent)}"/>')
        lines.append("  </owl:Class>")
        lines.append("")

    for prop in datatype_properties:
        if not isinstance(prop, dict):
            continue
        name = _safe_name(prop.get("id") or prop.get("name") or prop.get("label"), "property")
        label = str(prop.get("label") or name)
        domain = _safe_name(prop.get("domain") or "EducationResource")
        description = str(prop.get("description") or "")
        lines.append(f'  <owl:DatatypeProperty rdf:about="{_resource(name)}">')
        lines.append(f"    <rdfs:label>{escape(label)}</rdfs:label>")
        if description:
            lines.append(f"    <rdfs:comment>{escape(description)}</rdfs:comment>")
        _append_source_comment(lines, prop)
        lines.append(f'    <rdfs:domain rdf:resource="{_resource(domain)}"/>')
        lines.append(f'    <rdfs:range rdf:resource="{escape(_xsd_range(prop))}"/>')
        lines.append("  </owl:DatatypeProperty>")
        lines.append("")

    for prop in _dedupe_object_properties(object_properties):
        if not isinstance(prop, dict):
            continue
        name = _safe_name(prop.get("id") or prop.get("name") or prop.get("predicate") or prop.get("type"), "relation")
        label = str(prop.get("label") or name)
        domain = _safe_name(prop.get("domain") or prop.get("source") or prop.get("subject"), "EducationResource")
        range_ = _safe_name(prop.get("range") or prop.get("target") or prop.get("object"), "EducationResource")
        description = str(prop.get("description") or prop.get("reason") or "")
        lines.append(f'  <owl:ObjectProperty rdf:about="{_resource(name)}">')
        lines.append(f"    <rdfs:label>{escape(label)}</rdfs:label>")
        if description:
            lines.append(f"    <rdfs:comment>{escape(description)}</rdfs:comment>")
        _append_source_comment(lines, prop)
        lines.append(f'    <rdfs:domain rdf:resource="{_resource(domain)}"/>')
        lines.append(f'    <rdfs:range rdf:resource="{_resource(range_)}"/>')
        lines.append("  </owl:ObjectProperty>")
        lines.append("")

    lines.append("</rdf:RDF>")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    validate_owl_file(str(output_path))
    return str(output_path)


def validate_owl_file(file_path: str) -> bool:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"OWL 文件不存在：{file_path}")
    try:
        from rdflib import Graph
    except ImportError:
        return True
    try:
        Graph().parse(str(path), format="xml")
    except Exception as exc:
        raise RuntimeError(f"OWL/RDF 文件校验失败：{exc}") from exc
    return True


def _object_properties_from_relations(relations: list) -> list:
    result = []
    for relation in relations if isinstance(relations, list) else []:
        if not isinstance(relation, dict):
            continue
        subject = relation.get("subject") or relation.get("source")
        obj = relation.get("object") or relation.get("target")
        predicate = relation.get("predicate") or relation.get("type")
        if subject and obj and predicate:
            result.append({
                "id": predicate,
                "label": relation.get("label") or predicate,
                "domain": subject,
                "range": obj,
                "description": relation.get("description") or relation.get("reason") or "",
                "source_record_ids": relation.get("source_record_ids", []),
                "evidence": relation.get("evidence", []),
            })
    return result


def _hierarchy_map(items: list) -> dict:
    result: dict[str, list[str]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        parent = _safe_name(item.get("parent"), "")
        child = _safe_name(item.get("child"), "")
        if parent and child:
            result.setdefault(child, []).append(parent)
    return result


def _ontology_metadata_lines(ontology: dict) -> list[str]:
    metadata = ontology.get("metadata", {}) if isinstance(ontology.get("metadata", {}), dict) else {}
    alignment_stats = metadata.get("alignment_stats", {}) if isinstance(metadata.get("alignment_stats", {}), dict) else {}
    lines: list[str] = []
    values = {
        "generationMode": metadata.get("generation_mode"),
        "sourceFileCount": metadata.get("source_file_count"),
        "alignmentClassMappings": alignment_stats.get("class_mappings"),
        "alignmentPropertyMappings": alignment_stats.get("property_mappings"),
        "alignmentRelationMappings": alignment_stats.get("relation_mappings"),
        "createdAt": metadata.get("created_at") or datetime.now().isoformat(timespec="seconds"),
    }
    for key, value in values.items():
        if value not in (None, ""):
            lines.append(f"    <edu:{key}>{escape(str(value))}</edu:{key}>")
    return lines


def _append_source_comment(lines: list[str], item: dict) -> None:
    ids = item.get("source_record_ids")
    if isinstance(ids, list) and ids:
        lines.append(f"    <rdfs:comment>{escape('source_record_ids=' + ','.join(map(str, ids[:20])))}</rdfs:comment>")
        lines.append(f"    <edu:sourceRecordIds>{escape(','.join(map(str, ids)))}</edu:sourceRecordIds>")
    if item.get("source_doc"):
        lines.append(f"    <edu:sourceDoc>{escape(str(item.get('source_doc')))}</edu:sourceDoc>")
    if item.get("source_table"):
        lines.append(f"    <edu:sourceTable>{escape(str(item.get('source_table')))}</edu:sourceTable>")
    sources = item.get("sources") if isinstance(item.get("sources"), list) else []
    source = item.get("source") if isinstance(item.get("source"), dict) else None
    if source:
        sources = [source, *sources]
    if sources:
        lines.append(f"    <edu:sourcesJson>{escape(json.dumps(sources, ensure_ascii=False))}</edu:sourcesJson>")
    for source_item in sources[:20]:
        if not isinstance(source_item, dict):
            continue
        file_path = source_item.get("file_path") or source_item.get("source_file")
        filename = source_item.get("filename") or (Path(str(file_path)).name if file_path else "")
        if file_path:
            lines.append(f"    <edu:sourceFile>{escape(str(file_path))}</edu:sourceFile>")
        if filename:
            lines.append(f"    <edu:sourceFilename>{escape(str(filename))}</edu:sourceFilename>")
        if source_item.get("page") not in (None, ""):
            lines.append(f"    <edu:sourcePage>{escape(str(source_item.get('page')))}</edu:sourcePage>")
        if source_item.get("table_index") not in (None, ""):
            lines.append(f"    <edu:sourceTable>{escape(str(source_item.get('table_index')))}</edu:sourceTable>")
        if source_item.get("row_index") not in (None, ""):
            lines.append(f"    <edu:sourceRow>{escape(str(source_item.get('row_index')))}</edu:sourceRow>")
    for file_path in item.get("source_files", []) if isinstance(item.get("source_files", []), list) else []:
        lines.append(f"    <edu:sourceFile>{escape(str(file_path))}</edu:sourceFile>")


def _dedupe_object_properties(items: list) -> list:
    seen = set()
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        marker = (
            _safe_name(item.get("domain") or item.get("subject") or item.get("source")),
            _safe_name(item.get("id") or item.get("predicate") or item.get("type")),
            _safe_name(item.get("range") or item.get("object") or item.get("target")),
        )
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


