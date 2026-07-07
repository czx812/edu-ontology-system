from fastapi import APIRouter, Depends

from api.auth import get_current_user
from services.log_service import (
    list_my_generations,
    list_my_operations,
    list_my_questions,
    write_operation_log,
)

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/my-operations")
def my_operations(user: dict = Depends(get_current_user)) -> dict:
    write_operation_log(user=user, action="VIEW_LOGS", method="GET", path="/logs/my-operations", detail="查看我的操作日志")
    return {"items": list_my_operations(user)}


@router.get("/my-generations")
def my_generations(user: dict = Depends(get_current_user)) -> dict:
    write_operation_log(user=user, action="VIEW_GENERATION_RECORDS", method="GET", path="/logs/my-generations", detail="查看我的本体生成记录")
    return {"items": list_my_generations(user)}


@router.get("/my-questions")
def my_questions(user: dict = Depends(get_current_user)) -> dict:
    write_operation_log(user=user, action="VIEW_LOGS", method="GET", path="/logs/my-questions", detail="查看我的提问记录")
    return {"items": list_my_questions(user)}
