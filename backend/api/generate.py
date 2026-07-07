from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from config import settings
from core.workflow import ModuleNotReadyError, run_workflow


router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    file_path: str


def generate_ontology(file_path: str, user_id: str) -> dict:
    """Run the full PDF -> structured data -> ontology -> OWL workflow."""
    export_dir = settings.EXPORT_DIR / str(user_id)
    export_dir.mkdir(parents=True, exist_ok=True)
    state = run_workflow({"file_path": file_path, "export_dir": str(export_dir)})
    clean_data = state.get("clean_data", {}) if isinstance(state.get("clean_data", {}), dict) else {}
    ontology = state.get("ontology", {})
    relations = ontology.get("relations", []) if isinstance(ontology, dict) else []
    metadata = ontology.get("metadata", {}) if isinstance(ontology, dict) else {}
    warnings = list(ontology.get("warnings", [])) if isinstance(ontology, dict) else []
    if not relations:
        warning = "当前大模型未识别出对象关系，OWL 中不会生成 owl:ObjectProperty。"
        if warning not in warnings:
            warnings.append(warning)
    generation_mode = metadata.get("generation_mode", "llm")
    return {
        "ontology": {
            "classes": ontology.get("classes", []),
            "properties": ontology.get("properties", []),
            "relations": relations,
        },
        "owl_file": state.get("owl_file", ""),
        "stats": {
            "classes": len(ontology.get("classes", [])),
            "datatype_properties": len(ontology.get("properties", [])),
            "object_properties": len(relations),
            "relations": len(relations),
            "generation_mode": generation_mode,
        },
        "warnings": warnings,
        "errors": state.get("errors", []),
    }


@router.post("/generate")
def generate(request: GenerateRequest, user: dict = Depends(get_current_user)) -> dict:
    try:
        result = generate_ontology(request.file_path, user["id"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ModuleNotReadyError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成失败：{exc}") from exc

    return {
        **result,
        "status": "success",
    }
