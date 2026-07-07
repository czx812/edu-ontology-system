from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from config import settings
from core.workflow import ModuleNotReadyError, run_workflow


router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    file_path: str


def generate_ontology(file_path: str, user_id: str) -> dict:
    """
    输入：PDF路径或上传后的PDF文件名
    输出：
    {
        "ontology": dict,
        "owl_file": str
    }
    """
    export_dir = settings.EXPORT_DIR / str(user_id)
    export_dir.mkdir(parents=True, exist_ok=True)
    state = run_workflow({"file_path": file_path, "export_dir": str(export_dir)})
    return {
        "ontology": state.get("ontology", {}),
        "owl_file": state.get("owl_file", ""),
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
