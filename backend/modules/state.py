from typing import Any, Dict, TypedDict


class OntologyState(TypedDict):
    file_path: str
    raw_text: str
    clean_data: Dict[str, Any]
    ontology: Dict[str, Any]
    trace_map: Dict[str, Any]
    trace_file: str
    owl_file: str


def create_state() -> OntologyState:
    return {
        "file_path": "",
        "raw_text": "",
        "clean_data": {},
        "ontology": {},
        "trace_map": {},
        "trace_file": "",
        "owl_file": "",
    }