import hashlib
import hmac
import json
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from config import settings


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthStore:
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = Path(storage_path or settings.DATA_DIR / "auth" / "users.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._users: Dict[str, Dict[str, Any]] = {}
        self._tokens: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        self._users = payload.get("users", {})

    def _save(self) -> None:
        payload = {"users": self._users}
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _hash_password(self, password: str) -> Dict[str, str]:
        salt = secrets.token_hex(8)
        encoded = password.encode("utf-8")
        digest = hashlib.pbkdf2_hmac("sha256", encoded, salt.encode("utf-8"), 200000).hex()
        return {"salt": salt, "hash": digest}

    def _verify_password_hash(self, password: str, salt: str, expected_hash: str) -> bool:
        encoded = password.encode("utf-8")
        digest = hashlib.pbkdf2_hmac("sha256", encoded, salt.encode("utf-8"), 200000).hex()
        return hmac.compare_digest(digest, expected_hash)

    def _public_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        username = user.get("username", "")
        role = user.get("role") or ("admin" if username == "admin" else "user")
        return {
            "id": user.get("id"),
            "username": username,
            "role": role,
            "is_admin": bool(user.get("is_admin") or role == "admin" or username == "admin"),
        }

    def register_user(self, username: str, password: str) -> Dict[str, Any]:
        username = (username or "").strip()
        password = (password or "").strip()
        if not username or not password:
            raise ValueError("用户名和密码不能为空")
        if username in self._users:
            raise ValueError("用户名已存在")

        user_id = str(len(self._users) + 1)
        password_info = self._hash_password(password)
        user = {
            "id": user_id,
            "username": username,
            "password_hash": password_info["hash"],
            "password_salt": password_info["salt"],
            "role": "admin" if username == "admin" else "user",
        }
        self._users[username] = user
        self._save()
        return self._public_user(user)

    def verify_password(self, username: str, password: str) -> bool:
        user = self._users.get((username or "").strip())
        if not user:
            return False
        return self._verify_password_hash(password, user.get("password_salt", ""), user.get("password_hash", ""))

    def create_token(self, user_id: str) -> str:
        token = secrets.token_hex(24)
        self._tokens[token] = str(user_id)
        return token

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        user_id = self._tokens.get(token)
        if not user_id:
            return None
        for user in self._users.values():
            if user.get("id") == user_id:
                return self._public_user(user)
        return None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        user = self._users.get((username or "").strip())
        if not user:
            return None
        return self._public_user(user)


auth_store = AuthStore()
router = APIRouter(tags=["auth"])


def get_auth_store() -> AuthStore:
    return auth_store


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    store: AuthStore = Depends(get_auth_store),
) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要登录后才能使用")
    token = authorization.split(" ", 1)[1].strip()
    user = store.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效")
    return user


@router.post("/auth/register")
def register(request: RegisterRequest) -> dict:
    try:
        user = auth_store.register_user(request.username, request.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = auth_store.create_token(user["id"])
    return {"user": user, "token": token}


@router.post("/auth/login")
def login(request: LoginRequest) -> dict:
    if not auth_store.verify_password(request.username, request.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user = auth_store.get_user_by_username(request.username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    token = auth_store.create_token(user["id"])
    return {"user": user, "token": token}


@router.get("/auth/me")
def me(user: Dict[str, Any] = Depends(get_current_user)) -> dict:
    return {"user": user}
