from typing import Any, Dict, TypedDict


class OntologyState(TypedDict):
    file_path: str
    raw_text: str
    clean_data: Dict[str, Any]
    entity_json: Dict[str, Any]
    semantic_model: Dict[str, Any]
    ontology: Dict[str, Any]
    owl_file: str


def create_state() -> OntologyState:
    return {
        "file_path": "",
        "raw_text": "",
        "clean_data": {},
        "entity_json": {},
        "semantic_model": {},
        "ontology": {},
        "owl_file": "",
    }
