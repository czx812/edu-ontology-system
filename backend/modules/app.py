import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from mock_data import get_mock_state
from schema_matcher import match_schema
from ontology_aligner import align_ontology
from owl_generator import generate_owl


if __name__ == "__main__":
    print("D module demo start")

    state = get_mock_state()
    state["clean_data"] = match_schema(state.get("clean_data", {}))
    state["ontology"] = align_ontology(state.get("ontology", {}))
    state["owl_file"] = generate_owl(state.get("ontology", {}))

    print("done")
    print("owl_file:", state["owl_file"])
