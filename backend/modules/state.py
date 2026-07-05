from typing import Any, Dict, TypedDict


class OntologyState(TypedDict):
    file_path: str
    raw_text: str
    clean_data: Dict[str, Any]
    ontology: Dict[str, Any]
    owl_file: str


def create_state() -> OntologyState:
    return {
        "file_path": "",
        "raw_text": "",
        "clean_data": {},
        "ontology": {},
        "owl_file": "",
    }