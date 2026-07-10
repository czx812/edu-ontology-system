from typing import Any, Dict, List, TypedDict


class OntologyState(TypedDict):
    file_path: str
    raw_text: str
    clean_data: Dict[str, Any]
    source_metadata: Dict[str, Any]
    standard_metadata: Dict[str, Any]
    entity_json: Dict[str, Any]
    semantic_model: Dict[str, Any]
    single_ontology: Dict[str, Any]
    ontology: Dict[str, Any]
    file_results: List[Dict[str, Any]]
    merged_ontology: Dict[str, Any]
    trace_map: Dict[str, Any]
    trace_file: str
    owl_file: str


def create_state() -> OntologyState:
    return {
        "file_path": "",
        "raw_text": "",
        "clean_data": {},
        # PDF 解析出的教育标准编码；绝不使用 LLM 本体内容替代。
        "source_metadata": {"classes": [], "properties": [], "relations": []},
        "standard_metadata": {"classes": [], "properties": [], "relations": []},
        "entity_json": {},
        "semantic_model": {},
        "single_ontology": {},
        "ontology": {},
        "file_results": [],
        "merged_ontology": {},
        "trace_map": {},
        "trace_file": "",
        "owl_file": "",
    }
