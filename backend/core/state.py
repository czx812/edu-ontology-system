"""Shared state shape for the PDF source data and generated ontology."""

from typing import Any, Dict, List, TypedDict


class SourceMetadata(TypedDict):
    classes: List[Dict[str, Any]]
    properties: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]


class OntologyState(TypedDict, total=False):
    file_path: str
    raw_text: str
    clean_data: Dict[str, Any]
    source_metadata: SourceMetadata
    standard_metadata: SourceMetadata
    ontology: Dict[str, Any]


def create_state() -> OntologyState:
    return {
        "file_path": "",
        "raw_text": "",
        "clean_data": {},
        "source_metadata": {"classes": [], "properties": [], "relations": []},
        "standard_metadata": {"classes": [], "properties": [], "relations": []},
        "ontology": {},
    }
