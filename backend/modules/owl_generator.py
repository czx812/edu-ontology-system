from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from config import settings


XSD_RANGES = {
    "string": "string",
    "integer": "integer",
    "int": "integer",
    "float": "decimal",
    "decimal": "decimal",
    "number": "decimal",
    "date": "date",
    "datetime": "dateTime",
    "boolean": "boolean",
    "bool": "boolean",
}


def _safe_name(name: str) -> str:
    name = str(name or "").strip()
    if not name:
        return "Unnamed"
    return (
        name.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


def _xsd_range(value: str) -> str:
    key = str(value or "string").strip().lower()
    return XSD_RANGES.get(key, "string")


def generate_owl(ontology: dict, export_dir: str | None = None) -> str:
    """Generate OWL with separated Class, DatatypeProperty, and ObjectProperty."""
    classes = ontology.get("classes", [])
    relations = ontology.get("relations", [])
    properties = ontology.get("properties", [])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(export_dir) if export_dir else settings.EXPORT_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"ontology_{timestamp}.owl"

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<rdf:RDF')
    lines.append('  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"')
    lines.append('  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"')
    lines.append('  xmlns:owl="http://www.w3.org/2002/07/owl#"')
    lines.append('  xmlns:xsd="http://www.w3.org/2001/XMLSchema#"')
    lines.append('  xmlns:edu="http://example.org/edu-ontology#">')
    lines.append("")
    lines.append('  <owl:Ontology rdf:about="http://example.org/edu-ontology"/>')
    lines.append("")

    for cls in classes:
        if isinstance(cls, dict):
            name = _safe_name(cls.get("name"))
            label = cls.get("label", name)
            description = cls.get("description", "")
        else:
            name = _safe_name(cls)
            label = name
            description = ""

        lines.append(f'  <owl:Class rdf:about="http://example.org/edu-ontology#{escape(name)}">')
        lines.append(f"    <rdfs:label>{escape(str(label))}</rdfs:label>")
        if description:
            lines.append(f"    <rdfs:comment>{escape(str(description))}</rdfs:comment>")
        lines.append("  </owl:Class>")
        lines.append("")

    for prop in properties:
        if not isinstance(prop, dict):
            continue
        name = _safe_name(prop.get("name", "property"))
        label = prop.get("label", name)
        domain = _safe_name(prop.get("domain") or "EducationResource")
        range_name = _xsd_range(prop.get("range", "string"))
        description = prop.get("description", "")

        lines.append(f'  <owl:DatatypeProperty rdf:about="http://example.org/edu-ontology#{escape(name)}">')
        lines.append(f"    <rdfs:label>{escape(str(label))}</rdfs:label>")
        if description:
            lines.append(f"    <rdfs:comment>{escape(str(description))}</rdfs:comment>")
        lines.append(f'    <rdfs:domain rdf:resource="http://example.org/edu-ontology#{escape(domain)}"/>')
        lines.append(f'    <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#{escape(range_name)}"/>')
        lines.append("  </owl:DatatypeProperty>")
        lines.append("")

    for relation in relations:
        if not isinstance(relation, dict):
            continue
        subject = _safe_name(relation.get("subject") or relation.get("source"))
        predicate = _safe_name(relation.get("predicate") or relation.get("type"))
        obj = _safe_name(relation.get("object") or relation.get("target"))
        label = relation.get("label") or predicate
        description = relation.get("description", "")
        relation_name = f"{subject}_{predicate}_{obj}"

        lines.append(f'  <owl:ObjectProperty rdf:about="http://example.org/edu-ontology#{escape(relation_name)}">')
        lines.append(f"    <rdfs:label>{escape(str(label))}</rdfs:label>")
        if description:
            lines.append(f"    <rdfs:comment>{escape(str(description))}</rdfs:comment>")
        lines.append(f'    <rdfs:domain rdf:resource="http://example.org/edu-ontology#{escape(subject)}"/>')
        lines.append(f'    <rdfs:range rdf:resource="http://example.org/edu-ontology#{escape(obj)}"/>')
        lines.append("  </owl:ObjectProperty>")
        lines.append("")

    lines.append("</rdf:RDF>")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)
