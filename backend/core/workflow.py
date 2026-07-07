from importlib import import_module
from pathlib import Path
from typing import Any, Callable

from config import settings


class ModuleNotReadyError(RuntimeError):
    pass


DEFAULT_STATE = {
    "file_path": "",
    "export_dir": "",
    "raw_text": "",
    "tables": [],
    "clean_data": {},
    "structured_file": "",
    "entity_json": {},
    "semantic_model": {},
    "ontology": {},
    "owl_file": "",
    "errors": [],
}


def _merge_state(state: dict) -> dict:
    merged = DEFAULT_STATE.copy()
    merged.update(state or {})
    return merged


def _load_function(module_name: str, function_name: str) -> Callable[..., Any]:
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ModuleNotReadyError(f"模块还没准备好：{module_name}") from exc

    func = getattr(module, function_name, None)
    if not callable(func):
        raise ModuleNotReadyError(f"函数还没实现：{module_name}.{function_name}()")
    return func


def extract_node(state: dict) -> dict:
    state = _merge_state(state)
    parse_pdf = _load_function("modules.pdf_parser", "parse_pdf")
    return parse_pdf(state)


def clean_node(state: dict) -> dict:
    state = _merge_state(state)
    clean_data = _load_function("modules.data_cleaner", "clean_data")
    return clean_data(state)


def schema_match_node(state: dict) -> dict:
    state = _merge_state(state)
    match_schema = _load_function("modules.schema_matcher", "match_schema")
    state["clean_data"] = match_schema(state.get("clean_data", {}))
    return state


def entity_extract_node(state: dict) -> dict:
    state = _merge_state(state)
    extract_entities = _load_function("ai.entity_extractor", "extract_entities")
    state["entity_json"] = extract_entities(state["clean_data"])
    return state


def semantic_classify_node(state: dict) -> dict:
    state = _merge_state(state)
    semantic_classify = _load_function("modules.semantic_classifier", "semantic_classify")
    state["semantic_model"] = semantic_classify({
        "entity_json": state["entity_json"],
        "clean_data": state["clean_data"],
    })
    return state


def ontology_build_node(state: dict) -> dict:
    state = _merge_state(state)
    build_ontology = _load_function("modules.ontology_builder", "build_ontology")
    state["ontology"] = build_ontology(state)
    return state


def align_node(state: dict) -> dict:
    state = _merge_state(state)
    align_ontology = _load_function("modules.ontology_aligner", "align_ontology")
    state["ontology"] = align_ontology(state["ontology"])
    return state


def owl_generate_node(state: dict) -> dict:
    state = _merge_state(state)
    generate_owl = _load_function("modules.owl_generator", "generate_owl")
    export_dir = state.get("export_dir") or str(settings.EXPORT_DIR)
    state["owl_file"] = generate_owl(state["ontology"], export_dir=export_dir)
    return state


def run_workflow(state: dict) -> dict:
    """Full flow: PDF -> parse -> clean -> schema match -> ontology -> align -> OWL."""
    state = _merge_state(state)
    file_path = Path(state["file_path"])
    if not file_path.exists():
        file_path = settings.UPLOAD_DIR / file_path.name
    if not file_path.exists():
        raise FileNotFoundError(f"PDF文件不存在：{state['file_path']}")
    state["file_path"] = str(file_path)

    for node in (
        extract_node,
        clean_node,
        schema_match_node,
        ontology_build_node,
        align_node,
        owl_generate_node,
    ):
        state = node(state)

    return state
