from typing import Any, Dict, List, Tuple


def _class_key(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("label") or "").strip().lower()
    return str(item).strip().lower()


def _normalize_class(item: Any) -> Dict[str, str]:
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("label") or "").strip()
        label = str(item.get("label") or name).strip()
    else:
        name = str(item).strip()
        label = name

    return {
        "name": name,
        "label": label,
    }


def _relation_key(relation: Dict[str, Any]) -> Tuple[str, str, str]:
    subject = str(relation.get("subject", "")).strip().lower()
    predicate = str(
        relation.get("predicate")
        or relation.get("type")
        or relation.get("relation")
        or ""
    ).strip().lower()
    obj = str(relation.get("object", "")).strip().lower()
    return subject, predicate, obj


def _normalize_relation(relation: Dict[str, Any]) -> Dict[str, str]:
    return {
        "subject": str(relation.get("subject", "")).strip(),
        "predicate": str(
            relation.get("predicate")
            or relation.get("type")
            or relation.get("relation")
            or ""
        ).strip(),
        "object": str(relation.get("object", "")).strip(),
    }


def align_ontology(ontology: Dict[str, Any]) -> Dict[str, Any]:
    """
    输入：B模块生成的 ontology
    输出：规范化、去重后的 ontology

    期望 B 给你的 ontology 大概长这样：
    {
        "classes": [
            {"name": "School", "label": "学校"},
            {"name": "Student", "label": "学生"}
        ],
        "relations": [
            {"subject": "Student", "predicate": "belongsTo", "object": "School"}
        ],
        "properties": []
    }
    """

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
        if name and name.lower() not in property_seen:
            property_seen.add(name.lower())
            properties.append(prop)

    return {
        "classes": classes,
        "relations": relations,
        "properties": properties,
    }