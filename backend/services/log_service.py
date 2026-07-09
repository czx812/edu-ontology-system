from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import settings


OPERATION_COLUMNS = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    method TEXT,
    path TEXT,
    status_code INTEGER,
    ip TEXT,
    user_agent TEXT,
    duration_ms REAL,
    detail TEXT,
    created_at TEXT
"""

GENERATION_COLUMNS = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    file_name TEXT,
    file_path TEXT,
    structured_file TEXT,
    record_count INTEGER,
    owl_file TEXT,
    status TEXT,
    error_message TEXT,
    duration_ms REAL,
    created_at TEXT
"""

QUESTION_COLUMNS = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    question TEXT,
    answer TEXT,
    created_at TEXT
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _connect() -> sqlite3.Connection:
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_log_tables() -> None:
    try:
        with _connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS operation_logs ({OPERATION_COLUMNS})")
            conn.execute(f"CREATE TABLE IF NOT EXISTS generation_records ({GENERATION_COLUMNS})")
            conn.execute(f"CREATE TABLE IF NOT EXISTS question_records ({QUESTION_COLUMNS})")
            conn.commit()
        settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
        settings.SYSTEM_LOG_FILE.touch(exist_ok=True)
        print("[日志管理] 日志数据表初始化完成")
        print(f"[日志管理] 系统日志文件：{_display_path(settings.SYSTEM_LOG_FILE)}")
    except Exception as exc:
        print(f"[日志管理] 初始化失败：{exc}")


def write_system_log(level: str, message: str) -> None:
    try:
        settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
        line = f"[{_now()}] [{str(level or 'INFO').upper()}] {_sanitize(message)}\n"
        with settings.SYSTEM_LOG_FILE.open("a", encoding="utf-8") as target:
            target.write(line)
    except Exception:
        pass


def write_operation_log(
    user: Any = None,
    action: str = "",
    method: str = "",
    path: str = "",
    status_code: int = 200,
    ip: str = "",
    user_agent: str = "",
    duration_ms: float = 0,
    detail: str = "",
) -> None:
    try:
        init_log_tables_quiet()
        user_id, username = _user_identity(user)
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO operation_logs
                (user_id, username, action, method, path, status_code, ip, user_agent, duration_ms, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    action or "HTTP_REQUEST",
                    method,
                    path,
                    status_code,
                    ip,
                    _sanitize(user_agent, 500),
                    duration_ms,
                    _sanitize(detail, 1000),
                    _now(),
                ),
            )
            conn.commit()
    except Exception as exc:
        write_system_log("ERROR", f"数据库异常：写入操作日志失败：{exc}")


def write_generation_record(
    user: Any = None,
    file_name: str = "",
    file_path: str = "",
    structured_file: str = "",
    record_count: int = 0,
    owl_file: str = "",
    status: str = "SUCCESS",
    error_message: str = "",
    duration_ms: float = 0,
) -> None:
    try:
        init_log_tables_quiet()
        user_id, username = _user_identity(user)
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO generation_records
                (user_id, username, file_name, file_path, structured_file, record_count, owl_file, status, error_message, duration_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    _sanitize(file_name, 300),
                    _sanitize(file_path, 1000),
                    _sanitize(structured_file, 1000),
                    int(record_count or 0),
                    _sanitize(owl_file, 1000),
                    status or "SUCCESS",
                    _sanitize(error_message, 1000),
                    duration_ms,
                    _now(),
                ),
            )
            conn.commit()
    except Exception as exc:
        write_system_log("ERROR", f"数据库异常：写入生成记录失败：{exc}")




def write_question_record(user: Any = None, question: Any = "", answer: Any = "") -> None:
    try:
        init_log_tables_quiet()
        user_id, username = _user_identity(user)
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO question_records
                (user_id, username, question, answer, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, _sanitize(question, 2000), _sanitize(answer, 4000), _now()),
            )
            conn.commit()
    except Exception as exc:
        write_system_log("ERROR", f"数据库异常：写入提问记录失败：{exc}")

def init_log_tables_quiet() -> None:
    try:
        with _connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS operation_logs ({OPERATION_COLUMNS})")
            conn.execute(f"CREATE TABLE IF NOT EXISTS generation_records ({GENERATION_COLUMNS})")
            conn.execute(f"CREATE TABLE IF NOT EXISTS question_records ({QUESTION_COLUMNS})")
            conn.commit()
    except Exception:
        pass


def list_my_operations(user: Any, limit: int = 100) -> List[Dict[str, Any]]:
    user_id, username = _user_identity(user)
    return _query_list(
        "SELECT id, action, method, path, status_code, duration_ms, detail, created_at FROM operation_logs WHERE user_id = ? OR username = ? ORDER BY id DESC LIMIT ?",
        (user_id, username, limit),
    )


def list_my_generations(user: Any, limit: int = 100) -> List[Dict[str, Any]]:
    user_id, username = _user_identity(user)
    return _query_list(
        "SELECT id, file_name, file_path, structured_file, record_count, owl_file, status, error_message, duration_ms, created_at FROM generation_records WHERE user_id = ? OR username = ? ORDER BY id DESC LIMIT ?",
        (user_id, username, limit),
    )


def list_my_questions(user: Any, limit: int = 100) -> List[Dict[str, Any]]:
    user_id, username = _user_identity(user)
    return _query_list(
        "SELECT id, question, answer, created_at FROM question_records WHERE user_id = ? OR username = ? ORDER BY id DESC LIMIT ?",
        (user_id, username, limit),
    )


def list_admin_operations(page: int = 1, page_size: int = 20, action: str = "", username: str = "") -> Dict[str, Any]:
    where, params = _filters(("action", action), ("username", username))
    return _paged("operation_logs", where, params, page, page_size)


def list_admin_generations(page: int = 1, page_size: int = 20, status: str = "", username: str = "") -> Dict[str, Any]:
    where, params = _filters(("status", status), ("username", username))
    return _paged("generation_records", where, params, page, page_size)


def list_admin_questions(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    return _paged("question_records", "", [], page, page_size)


def read_system_log_lines(limit: int = 200) -> List[str]:
    try:
        if not settings.SYSTEM_LOG_FILE.exists():
            return []
        return settings.SYSTEM_LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
    except Exception:
        return []


def _query_list(sql: str, params: Tuple[Any, ...]) -> List[Dict[str, Any]]:
    try:
        init_log_tables_quiet()
        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        write_system_log("ERROR", f"数据库异常：查询日志失败：{exc}")
        return []


def _paged(table: str, where: str, params: List[Any], page: int, page_size: int) -> Dict[str, Any]:
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    offset = (page - 1) * page_size
    try:
        init_log_tables_quiet()
        with _connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) AS total FROM {table} {where}", params).fetchone()["total"]
            rows = conn.execute(
                f"SELECT * FROM {table} {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                [*params, page_size, offset],
            ).fetchall()
        return {"total": total, "items": [dict(row) for row in rows]}
    except Exception as exc:
        write_system_log("ERROR", f"数据库异常：分页查询失败：{exc}")
        return {"total": 0, "items": []}


def _filters(*pairs: Tuple[str, str]) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    for column, value in pairs:
        text = str(value or "").strip()
        if text:
            clauses.append(f"{column} LIKE ?")
            params.append(f"%{text}%")
    return ("WHERE " + " AND ".join(clauses), params) if clauses else ("", [])


def _user_identity(user: Any) -> Tuple[Optional[int], str]:
    if user is None:
        return None, "anonymous"
    if isinstance(user, dict):
        raw_id = user.get("id") or user.get("user_id")
        username = user.get("username") or user.get("name") or "anonymous"
    else:
        raw_id = getattr(user, "id", None) or getattr(user, "user_id", None)
        username = getattr(user, "username", None) or getattr(user, "name", None) or "anonymous"
    try:
        user_id = int(raw_id) if raw_id is not None else None
    except (TypeError, ValueError):
        user_id = None
    return user_id, str(username or "anonymous")


def _sanitize(value: Any, limit: int = 2000) -> str:
    text = str(value or "")
    for key in ("password", "api_key", "apikey", "authorization", "token"):
        text = text.replace(key, "[redacted]")
    return text[:limit]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(settings.PROJECT_DIR)).replace("\\", "/")
    except ValueError:
        return str(path)

