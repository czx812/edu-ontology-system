from __future__ import annotations

import json
import tempfile
from pathlib import Path

from modules.batch_ontology_aligner import cross_file_ontology_align
from modules.ontology_merger import merge_ontologies
from modules.owl_generator import generate_owl, validate_owl_file


def sample_ontology(file_path: str, label_suffix: str = "") -> dict:
    source = {"file_path": file_path, "filename": Path(file_path).name, "page": 11, "table_index": 0, "row_index": 2}
    return {
        "classes": [{"id": "EducationResource", "name": "EducationResource", "label": "Education Resource"}],
        "datatype_properties": [
            {
                "id": "jctb010101",
                "code": "JCTB010101",
                "name": "yzbm",
                "field_name": "YZBM",
                "label": "邮政编码" + label_suffix,
                "domain": "EducationResource",
                "range": "string",
                "source": source,
                "sources": [source],
                "source_files": [file_path],
            },
            {
                "id": "xm" + label_suffix.lower(),
                "code": "",
                "name": "xm",
                "field_name": "XM",
                "label": "姓名",
                "domain": "EducationResource",
                "range": "string",
                "source": source,
                "sources": [source],
                "source_files": [file_path],
            },
        ],
        "properties": [],
        "relations": [],
        "metadata": {"source_docs": [file_path]},
        "stats": {"classes": 1, "datatype_properties": 2, "relations": 0},
    }


def main() -> None:
    ontologies = [sample_ontology("backend/data/uploads/file1.pdf"), sample_ontology("backend/data/uploads/file2.pdf", "")]
    alignment = cross_file_ontology_align(ontologies)
    assert alignment["class_mappings"], "class_mappings should not be empty"
    assert any(item.get("source_code") == "JCTB010101" and item.get("relation") == "same_as" for item in alignment["property_mappings"]), "same code should align"

    merged = merge_ontologies(ontologies, alignment)
    props = merged.get("datatype_properties", [])
    assert len(props) == 2, f"expected duplicate code to merge, got {len(props)}"
    merged_code = next(item for item in props if item.get("code") == "JCTB010101")
    assert len(merged_code.get("source_files", [])) == 2, "source_files should be preserved"
    assert not any(any(ch.isdigit() for ch in cls.get("id", "")) and cls.get("id", "").upper() == cls.get("id", "") for cls in merged.get("classes", [])), "code-like classes should not be created"

    with tempfile.TemporaryDirectory() as tmp:
        owl = generate_owl(merged, export_dir=tmp)
        validate_owl_file(owl)
        text = Path(owl).read_text(encoding="utf-8")
        assert text.count("prop_JCTB010101") <= 1
        assert "sourceFile" in text and "sourcesJson" in text
        Path(tmp, "merged.json").write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")

    print("batch alignment test passed")


if __name__ == "__main__":
    main()
