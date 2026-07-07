from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.workflow import ModuleNotReadyError, run_workflow


router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    file_path: str


def generate_ontology(file_path: str) -> dict:
    """
    输入：PDF路径或上传后的PDF文件名
    输出：
    {
        "ontology": dict,
        "owl_file": str
    }
    """
    state = run_workflow({"file_path": file_path})
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
    }


@router.post("/generate")
def generate(request: GenerateRequest) -> dict:
    try:
        result = generate_ontology(request.file_path)
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
