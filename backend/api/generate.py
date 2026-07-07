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
    return {
        "message": "本体生成成功",
        "ontology": state.get("ontology", {}),
        "structured_file": state.get("structured_file", ""),
        "record_count": clean_data.get("record_count", 0),
        "owl_file": state.get("owl_file", ""),
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
