from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from config import settings


def _safe_name(name: str) -> str:
    name = str(name or "").strip()
    if not name:
        return "Unnamed"
    return (
        name.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace(":", "_")
    )


def generate_owl(ontology: dict) -> str:
    """
    杈撳叆:align_ontology() 涔嬪悗鐨?ontology
    杈撳嚭锛氱敓鎴愮殑 owl 鏂囦欢璺緞
    """

    classes = ontology.get("classes", [])
    relations = ontology.get("relations", [])
    properties = ontology.get("properties", [])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = settings.EXPORT_DIR / f"ontology_{timestamp}.owl"

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<rdf:RDF')
    lines.append('  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"')
    lines.append('  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"')
    lines.append('  xmlns:owl="http://www.w3.org/2002/07/owl#"')
    lines.append('  xmlns:edu="http://example.org/edu-ontology#">')
    lines.append("")
    lines.append('  <owl:Ontology rdf:about="http://example.org/edu-ontology"/>')
    lines.append("")

    for cls in classes:
        if isinstance(cls, dict):
            name = _safe_name(cls.get("name"))
            label = cls.get("label", name)
        else:
            name = _safe_name(cls)
            label = name

        lines.append(f'  <owl:Class rdf:about="http://example.org/edu-ontology#{escape(name)}">')
        lines.append(f"    <rdfs:label>{escape(str(label))}</rdfs:label>")
        lines.append("  </owl:Class>")
        lines.append("")

    for prop in properties:
        name = _safe_name(prop.get("name", "property"))
        label = prop.get("label", name)

        lines.append(f'  <owl:DatatypeProperty rdf:about="http://example.org/edu-ontology#{escape(name)}">')
        lines.append(f"    <rdfs:label>{escape(str(label))}</rdfs:label>")
        lines.append("  </owl:DatatypeProperty>")
        lines.append("")

    for relation in relations:
        subject = _safe_name(relation.get("subject") or relation.get("source"))
        predicate = _safe_name(relation.get("predicate") or relation.get("type"))
        obj = _safe_name(relation.get("object") or relation.get("target"))

        relation_name = f"{subject}_{predicate}_{obj}"

        lines.append(f'  <owl:ObjectProperty rdf:about="http://example.org/edu-ontology#{escape(relation_name)}">')
        lines.append(f"    <rdfs:label>{escape(predicate)}</rdfs:label>")
        lines.append(f'    <rdfs:domain rdf:resource="http://example.org/edu-ontology#{escape(subject)}"/>')
        lines.append(f'    <rdfs:range rdf:resource="http://example.org/edu-ontology#{escape(obj)}"/>')
        lines.append("  </owl:ObjectProperty>")
        lines.append("")

    lines.append("</rdf:RDF>")

    output_path.write_text("\n".join(lines), encoding="utf-8")

    return output_path.name
