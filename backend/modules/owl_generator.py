from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from pathlib import Path
from xml.sax.saxutils import escape

try:
    from config import settings
except ModuleNotFoundError:  # Allows importing as backend.modules.owl_generator.
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
    """Infer a full XSD range URI from field semantics."""
    text = f"{label} {name} {description}"
    if any(word in text for word in ("日期", "日", "出生日期", "入学年月", "建校年月", "出版日期", "评定日期")):
        return XSD_RANGES["date"]
    if "时间" in text:
        return XSD_RANGES["time"]
    if any(word in text for word in ("人数", "人口", "数量", "层数", "页数", "个数", "时数")):
        return XSD_RANGES["integer"]
    if any(word in text for word in ("金额", "收入", "支出", "费用", "价格", "工资", "拨款", "债务", "经费", "面积", "单价")):
        return XSD_RANGES["decimal"]
    if any(word in text for word in ("是否", "标志", "正常", "不正常")):
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
    return infer_xsd_range(
        str(prop.get("label") or ""),
        str(prop.get("name") or ""),
        str(prop.get("description") or ""),
    )


def generate_owl(ontology: dict, export_dir: str | None = None) -> str:
    """Generate RDF/XML OWL from ontology JSON and validate it."""
    classes = ontology.get("classes", []) if isinstance(ontology, dict) else []
    properties = ontology.get("properties", []) if isinstance(ontology, dict) else []
    relations = ontology.get("relations", []) if isinstance(ontology, dict) else []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(export_dir) if export_dir else settings.EXPORT_DIR
    output_dir = Path(output_dir)
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
        f'  <owl:Ontology rdf:about="{escape(ONTOLOGY_DOC_URI)}"/>',
        "",
    ]

    for cls in classes:
        if not isinstance(cls, dict):
            continue
        name = _safe_name(cls.get("name"))
        label = str(cls.get("label") or name)
        description = str(cls.get("description") or "")
        parent = _safe_name(cls.get("parent"), "") if cls.get("parent") else ""

        lines.append(f'  <owl:Class rdf:about="{_resource(name)}">')
        lines.append(f"    <rdfs:label>{escape(label)}</rdfs:label>")
        if description:
            lines.append(f"    <rdfs:comment>{escape(description)}</rdfs:comment>")
        if parent and parent != name:
            lines.append(f'    <rdfs:subClassOf rdf:resource="{_resource(parent)}"/>')
        lines.append("  </owl:Class>")
        lines.append("")

    for prop in properties:
        if not isinstance(prop, dict):
            continue
        name = _safe_name(prop.get("name"), "property")
        label = str(prop.get("label") or name)
        domain = _safe_name(prop.get("domain") or "EducationResource")
        description = str(prop.get("description") or "")
        range_uri = _xsd_range(prop)

        lines.append(f'  <owl:DatatypeProperty rdf:about="{_resource(name)}">')
        lines.append(f"    <rdfs:label>{escape(label)}</rdfs:label>")
        if description:
            lines.append(f"    <rdfs:comment>{escape(description)}</rdfs:comment>")
        lines.append(f'    <rdfs:domain rdf:resource="{_resource(domain)}"/>')
        lines.append(f'    <rdfs:range rdf:resource="{escape(range_uri)}"/>')
        lines.append("  </owl:DatatypeProperty>")
        lines.append("")

    for relation in relations:
        if not isinstance(relation, dict):
            continue
        source = _safe_name(relation.get("source") or relation.get("subject"))
        target = _safe_name(relation.get("target") or relation.get("object"))
        rel_type = _safe_name(relation.get("type") or relation.get("predicate"), "relation")
        if not source or not target or not rel_type:
            continue
        label = str(relation.get("label") or rel_type)
        description = str(relation.get("description") or relation.get("reason") or "")
        relation_name = _safe_name(f"{source}_{rel_type}_{target}")

        lines.append(f'  <owl:ObjectProperty rdf:about="{_resource(relation_name)}">')
        lines.append(f"    <rdfs:label>{escape(label)}</rdfs:label>")
        if description:
            lines.append(f"    <rdfs:comment>{escape(description)}</rdfs:comment>")
        lines.append(f'    <rdfs:domain rdf:resource="{_resource(source)}"/>')
        lines.append(f'    <rdfs:range rdf:resource="{_resource(target)}"/>')
        lines.append("  </owl:ObjectProperty>")
        lines.append("")

    lines.append("</rdf:RDF>")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    validate_owl_file(str(output_path))
    return str(output_path)


def validate_owl_file(file_path: str) -> bool:
    """Validate generated RDF/XML with rdflib."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"OWL 文件不存在：{file_path}")
    try:
        from rdflib import Graph
    except ImportError as exc:
        raise RuntimeError("缺少 rdflib，无法校验 OWL 文件。请安装 rdflib。") from exc

    try:
        Graph().parse(str(path), format="xml")
    except Exception as exc:
        raise RuntimeError(f"OWL/RDF 文件校验失败：{exc}") from exc
    return True
