from typing import Dict, Any

def create_state() -> Dict[str, Any]:
    return {
        "file_path": "",
        "raw_text": "",
        "clean_data": {},
        "ontology": {},
        "owl_file": ""
    }