from __future__ import annotations

import time
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from api.auth import auth_store
from services.log_service import write_operation_log, write_system_log

EXCLUDED_PATHS = {"/docs", "/openapi.json", "/redoc", "/favicon.ico"}


def infer_action(path: str) -> str:
    if path.startswith("/api/upload") or path == "/upload":
        return "UPLOAD_PDF"
    if path.startswith("/api/generate") or path == "/generate":
        return "GENERATE_ONTOLOGY"
    if path.startswith("/api/export") or path == "/export":
        return "EXPORT_OWL"
    if path.startswith("/api/logs") or path.startswith("/logs"):
        return "VIEW_LOGS"
    if path.startswith("/api/admin") or path.startswith("/admin"):
        return "ADMIN_OPERATION"
    return "HTTP_REQUEST"


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500
        user = _user_from_request(request)
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            write_system_log("ERROR", f"接口异常：{request.method} {request.url.path} {exc}")
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            try:
                write_operation_log(
                    user=user,
                    action=infer_action(request.url.path),
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    ip=request.client.host if request.client else "",
                    user_agent=request.headers.get("user-agent", ""),
                    duration_ms=duration_ms,
                    detail="HTTP request",
                )
            except Exception:
                pass


def _user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    try:
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            return None
        token = authorization.split(" ", 1)[1].strip()
        return auth_store.get_user_by_token(token)
    except Exception:
        return None
