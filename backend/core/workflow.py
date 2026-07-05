from importlib import import_module
from pathlib import Path
from typing import Any, Callable


class ModuleNotReadyError(RuntimeError):
    pass


DEFAULT_STATE = {
    "file_path": "",
    "raw_text": "",
    "clean_data": {},
    "ontology": {},
    "owl_file": "",
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
    extract_pdf = _load_function("modules.pdf_parser", "extract_pdf")
    state["raw_text"] = extract_pdf(state["file_path"])
    return state


def clean_node(state: dict) -> dict:
    state = _merge_state(state)
    clean_data = _load_function("modules.data_cleaner", "clean_data")
    state["clean_data"] = clean_data(state["raw_text"])
    return state


def match_node(state: dict) -> dict:
    state = _merge_state(state)
    match_schema = _load_function("modules.schema_matcher", "match_schema")
    state["clean_data"] = match_schema(state["clean_data"])
    return state


def llm_node(state: dict) -> dict:
    state = _merge_state(state)
    build_ontology = _load_function("modules.ontology_builder", "build_ontology")
    state["ontology"] = build_ontology(state["clean_data"])
    return state


def align_node(state: dict) -> dict:
    state = _merge_state(state)
    align_ontology = _load_function("modules.ontology_aligner", "align_ontology")
    state["ontology"] = align_ontology(state["ontology"])
    return state


def owl_node(state: dict) -> dict:
    state = _merge_state(state)
    generate_owl = _load_function("modules.owl_generator", "generate_owl")
    state["owl_file"] = generate_owl(state["ontology"])
    return state


def run_workflow(state: dict) -> dict:
    """
    完整流程：
    PDF -> 清洗 -> 匹配 -> LLM -> OWL
    """
    state = _merge_state(state)
    file_path = Path(state["file_path"])
    if not file_path.exists():
        raise FileNotFoundError(f"PDF文件不存在:{state['file_path']}")

    for node in (extract_node, clean_node, match_node, llm_node, align_node, owl_node):
        state = node(state)

    return state
