from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.workflow import ModuleNotReadyError, run_workflow


router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    file_path: str


def generate_ontology(file_path: str) -> dict:
    """
    输入：PDF路径
    输出：
    {
        "ontology": dict,
        "owl_file": str
    }
    """
    state = run_workflow({"file_path": file_path})
    return {
        "ontology": state.get("ontology", {}),
        "owl_file": state.get("owl_file", ""),
    }


@router.post("/generate")
def generate(request: GenerateRequest) -> dict:
    try:
        result = generate_ontology(request.file_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModuleNotReadyError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    return {
        **result,
        "status": "success",
    }
