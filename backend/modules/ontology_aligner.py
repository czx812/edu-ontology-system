from typing import Any, Dict, Tuple


def _class_key(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("label") or "").strip().lower()
    return str(item).strip().lower()


def _normalize_class(item: Any) -> Dict[str, str]:
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("label") or "").strip()
        label = str(item.get("label") or name).strip()
        description = str(item.get("description") or "").strip()
    else:
        name = str(item).strip()
        label = name
        description = ""

    return {"name": name, "label": label, "description": description}


def _relation_key(relation: Dict[str, Any]) -> Tuple[str, str, str]:
    subject = str(relation.get("subject") or relation.get("source") or "").strip().lower()
    predicate = str(
        relation.get("predicate")
        or relation.get("type")
        or relation.get("relation")
        or ""
    ).strip().lower()
    obj = str(relation.get("object") or relation.get("target") or "").strip().lower()
    return subject, predicate, obj


def _normalize_relation(relation: Dict[str, Any]) -> Dict[str, str]:
    subject = str(relation.get("subject") or relation.get("source") or "").strip()
    predicate = str(
        relation.get("predicate")
        or relation.get("type")
        or relation.get("relation")
        or ""
    ).strip()
    obj = str(relation.get("object") or relation.get("target") or "").strip()
    label = str(relation.get("label") or predicate).strip()
    description = str(relation.get("description") or "").strip()
    return {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "source": subject,
        "type": predicate,
        "target": obj,
        "label": label,
        "description": description,
    }


def align_ontology(ontology: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and deduplicate B-layer ontology output for OWL generation."""
    raw_classes = ontology.get("classes", [])
    raw_relations = ontology.get("relations", [])
    raw_properties = ontology.get("properties", [])

    class_seen = set()
    classes = []
    for item in raw_classes:
        key = _class_key(item)
        if key and key not in class_seen:
            class_seen.add(key)
            classes.append(_normalize_class(item))

    relation_seen = set()
    relations = []
    for relation in raw_relations:
        if not isinstance(relation, dict):
            continue
        key = _relation_key(relation)
        if all(key) and key not in relation_seen:
            relation_seen.add(key)
            relations.append(_normalize_relation(relation))

    property_seen = set()
    properties = []
    for prop in raw_properties:
        if not isinstance(prop, dict):
            continue
        name = str(prop.get("name", "")).strip()
        domain = str(prop.get("domain", "")).strip()
        key = (domain.lower(), name.lower())
        if name and key not in property_seen:
            property_seen.add(key)
            properties.append(prop)

    return {"classes": classes, "relations": relations, "properties": properties}
