from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import get_current_user
from services.log_service import (
    list_admin_generations,
    list_admin_operations,
    list_admin_questions,
    read_system_log_lines,
    write_operation_log,
)

router = APIRouter(prefix="/admin/logs", tags=["admin-logs"])


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("is_admin") or user.get("role") == "admin" or user.get("username") == "admin":
        return user
    raise HTTPException(status_code=403, detail="需要管理员权限")


@router.get("/operations")
def operations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str = "",
    username: str = "",
    user: dict = Depends(require_admin),
) -> dict:
    write_operation_log(user=user, action="VIEW_LOGS", method="GET", path="/admin/logs/operations", detail="管理员查看操作日志")
    return list_admin_operations(page=page, page_size=page_size, action=action, username=username)


@router.get("/generations")
def generations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = "",
    username: str = "",
    user: dict = Depends(require_admin),
) -> dict:
    write_operation_log(user=user, action="VIEW_GENERATION_RECORDS", method="GET", path="/admin/logs/generations", detail="管理员查看生成记录")
    return list_admin_generations(page=page, page_size=page_size, status=status, username=username)


@router.get("/system")
def system_logs(user: dict = Depends(require_admin)) -> dict:
    write_operation_log(user=user, action="VIEW_LOGS", method="GET", path="/admin/logs/system", detail="管理员查看系统日志")
    return {"lines": read_system_log_lines(200)}


@router.get("/questions")
def questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
) -> dict:
    write_operation_log(user=user, action="VIEW_LOGS", method="GET", path="/admin/logs/questions", detail="管理员查看提问记录")
    return list_admin_questions(page=page, page_size=page_size)
