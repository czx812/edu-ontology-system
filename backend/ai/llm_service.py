"""Shared LLM API client and response parsing helpers."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


if load_dotenv:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)


LONGCAT_BASE_URL = "https://api.longcat.chat/openai/v1/chat/completions"
LONGCAT_MODEL = "LongCat-2.0"
DEFAULT_LLM_TIMEOUT = 180
DEFAULT_LLM_MAX_RETRIES = 3
DEFAULT_LLM_BATCH_SIZE = 30
DEFAULT_LLM_GROUP_MAX_RECORDS = 80
DEFAULT_LLM_MAX_CONCURRENCY = 3
PARSE_ERROR_TYPES = {"LLM_RESPONSE_PARSE_ERROR", "JSON_PARSE_ERROR", "EMPTY_CONTENT", "KEYERROR_CONTENT"}


class LLMServiceError(RuntimeError):
    """Raised when an LLM request fails."""

    def __init__(
        self,
        message: str,
        *,
        error_type: str = "LLM_SERVICE_ERROR",
        status_code: Optional[int] = None,
        content_preview: str = "",
        response_keys: Optional[list[str]] = None,
        choice_keys: Optional[list[str]] = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.content_preview = content_preview
        self.response_keys = response_keys or []
        self.choice_keys = choice_keys or []


class LLMResponseParseError(LLMServiceError):
    """Raised when content cannot be extracted from the provider response."""


class LLMJsonParseError(LLMServiceError):
    """Raised when extracted content cannot be parsed as JSON."""


class LLMService:
    """OpenAI-compatible chat completion client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self.provider = _provider_name()
        self.api_key = api_key or _configured_api_key(self.provider)
        self.base_url = base_url or _configured_base_url(self.provider)
        self.model = model or _configured_model(self.provider)
        self.timeout = timeout if timeout is not None else env_int("LLM_TIMEOUT", DEFAULT_LLM_TIMEOUT)
        self.max_retries = max(0, max_retries if max_retries is not None else env_int("LLM_MAX_RETRIES", DEFAULT_LLM_MAX_RETRIES))

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @property
    def api_key_suffix(self) -> str:
        if not self.api_key:
            return "EMPTY"
        return self.api_key[-4:]

    def config(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key_loaded": self.available,
            "api_key_suffix": self.api_key_suffix,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "batch_size": llm_batch_size(),
            "group_max_records": llm_group_max_records(),
            "max_concurrency": llm_max_concurrency(),
        }

    def print_config(self) -> None:
        print(f"[LLM CONFIG] provider={self.provider}")
        print(f"[LLM CONFIG] base_url={self.base_url}")
        print(f"[LLM CONFIG] model={self.model}")
        print(f"[LLM CONFIG] api_key_loaded={str(self.available).lower()}")
        print(f"[LLM CONFIG] api_key_suffix={self.api_key_suffix}")

    def chat(
        self,
        prompt: str,
        temperature: float = 0.2,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat_completion(messages, temperature=temperature, json_mode=json_mode)["content"]

    def chat_completion(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.2,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMServiceError(
                self._failure_message("MissingAPIKey", "LLM API key is not configured."),
                error_type="MissingAPIKey",
            )

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        raw_response, status_code = self._post_chat_completion(payload, timeout=timeout)
        content = extract_llm_content(raw_response)
        return {
            "content": content,
            "raw_response": raw_response,
            "provider": self.provider,
            "model": self.model,
            "status_code": status_code,
            "usage": raw_response.get("usage", {}),
            "response_keys": list(raw_response.keys()),
            "content_extract_ok": True,
        }

    def chat_json(self, prompt: str, temperature: float = 0.1) -> Dict[str, Any]:
        try:
            content = self.chat(prompt, temperature=temperature, json_mode=True)
        except LLMServiceError as exc:
            if "response_format" not in str(exc):
                raise
            content = self.chat(prompt, temperature=temperature, json_mode=False)
        return robust_json_parse(content)

    def _post_chat_completion(self, payload: Dict[str, Any], timeout: Optional[int] = None) -> tuple[Dict[str, Any], int]:
        last_exc: Optional[requests.exceptions.RequestException] = None
        attempts = max(1, self.max_retries + 1)
        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=timeout if timeout is not None else self.timeout,
                )
                response.raise_for_status()
                return response.json(), response.status_code
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                if attempt == attempts:
                    status_code = exc.response.status_code if getattr(exc, "response", None) is not None else None
                    error_type = type(exc).__name__
                    detail = _request_error_detail(exc)
                    raise LLMServiceError(
                        self._failure_message(error_type, detail),
                        error_type=error_type,
                        status_code=status_code,
                    ) from exc
                time.sleep(2)
        raise LLMServiceError(
            self._failure_message("RequestException", str(last_exc or "unknown error")),
            error_type="RequestException",
        )

    def _failure_message(self, error_type: str, detail: str) -> str:
        deepseek_warning = "\nwarning=base_url appears to be DeepSeek, expected LongCat." if "deepseek" in self.base_url.lower() else ""
        return (
            "LLM request failed after retries:\n"
            f"provider={self.provider}\n"
            f"base_url={self.base_url}\n"
            f"model={self.model}\n"
            f"key_suffix={self.api_key_suffix}\n"
            f"error_type={error_type}\n"
            f"error={detail}"
            f"{deepseek_warning}"
        )


def extract_llm_content(response_json: Dict[str, Any]) -> str:
    """Extract assistant content from common OpenAI-compatible variants."""
    if not isinstance(response_json, dict):
        raise LLMResponseParseError(
            "LLMResponseParseError: Cannot extract content from non-object response.",
            error_type="LLM_RESPONSE_PARSE_ERROR",
        )

    top_content = response_json.get("content")
    if isinstance(top_content, str) and top_content.strip():
        return top_content

    choices = response_json.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else {}
    choice_keys = list(choice.keys()) if isinstance(choice, dict) else []
    content = ""
    if isinstance(choice, dict):
        message = choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            content = message["content"]
        elif isinstance(message, dict) and isinstance(message.get("reasoning_content"), str):
            content = message["reasoning_content"]
        elif isinstance(choice.get("delta"), dict) and isinstance(choice["delta"].get("content"), str):
            content = choice["delta"]["content"]
        elif isinstance(choice.get("text"), str):
            content = choice["text"]

    if content and content.strip():
        return content

    response_keys = list(response_json.keys())
    if isinstance(top_content, str):
        raise LLMResponseParseError(
            "LLMResponseParseError: empty content.",
            error_type="EMPTY_CONTENT",
            response_keys=response_keys,
            choice_keys=choice_keys,
        )
    raise LLMResponseParseError(
        "LLMResponseParseError: Cannot extract content from response. "
        f"Available keys={response_keys}; choice_keys={choice_keys}",
        error_type="LLM_RESPONSE_PARSE_ERROR",
        response_keys=response_keys,
        choice_keys=choice_keys,
    )


def robust_json_parse(content: str) -> Dict[str, Any]:
    """Parse JSON even when it is wrapped in markdown or surrounded by text."""
    text = str(content or "").strip()
    if not text:
        raise LLMJsonParseError(
            "JSON_PARSE_ERROR: empty content",
            error_type="EMPTY_CONTENT",
            content_preview="",
        )

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    candidate = text[start : end + 1] if start >= 0 and end >= start else text
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        preview = text[:300]
        raise LLMJsonParseError(
            f"JSON_PARSE_ERROR: {exc}. content_preview={preview}",
            error_type="JSON_PARSE_ERROR",
            content_preview=preview,
        ) from exc
    if not isinstance(parsed, dict):
        raise LLMJsonParseError(
            f"JSON_PARSE_ERROR: expected object, got {type(parsed).__name__}. content_preview={text[:300]}",
            error_type="JSON_PARSE_ERROR",
            content_preview=text[:300],
        )
    return parsed


def extract_json_object(content: str) -> Dict[str, Any]:
    """Backward-compatible alias for robust JSON parsing."""
    return robust_json_parse(content)


def call_llm(prompt: str) -> str:
    return LLMService().chat(prompt)


def _provider_name() -> str:
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    return provider or "longcat"


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _configured_api_key(provider: str) -> str:
    if provider in {"", "longcat"}:
        return _env_first("LONGCAT_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    if provider == "openai":
        return _env_first("OPENAI_API_KEY", "LLM_API_KEY", "LONGCAT_API_KEY")
    return _env_first(f"{provider.upper()}_API_KEY", "LLM_API_KEY", "LONGCAT_API_KEY", "OPENAI_API_KEY")


def _configured_base_url(provider: str) -> str:
    if provider in {"", "longcat"}:
        return _env_first("LONGCAT_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", default=LONGCAT_BASE_URL)
    if provider == "openai":
        return _env_first("OPENAI_BASE_URL", "LLM_BASE_URL", "LONGCAT_BASE_URL", default=LONGCAT_BASE_URL)
    return _env_first(f"{provider.upper()}_BASE_URL", "LLM_BASE_URL", "LONGCAT_BASE_URL", "OPENAI_BASE_URL", default=LONGCAT_BASE_URL)


def _configured_model(provider: str) -> str:
    if provider in {"", "longcat"}:
        return _env_first("LONGCAT_MODEL", "LLM_MODEL", "OPENAI_MODEL", default=LONGCAT_MODEL)
    if provider == "openai":
        return _env_first("OPENAI_MODEL", "LLM_MODEL", "LONGCAT_MODEL", default=LONGCAT_MODEL)
    return _env_first(f"{provider.upper()}_MODEL", "LLM_MODEL", "LONGCAT_MODEL", "OPENAI_MODEL", default=LONGCAT_MODEL)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def llm_batch_size() -> int:
    return max(1, env_int("LLM_BATCH_SIZE", DEFAULT_LLM_BATCH_SIZE))


def llm_group_max_records() -> int:
    return max(1, env_int("LLM_GROUP_MAX_RECORDS", DEFAULT_LLM_GROUP_MAX_RECORDS))


def llm_max_concurrency() -> int:
    return max(1, env_int("LLM_MAX_CONCURRENCY", DEFAULT_LLM_MAX_CONCURRENCY))


def _request_error_detail(exc: requests.exceptions.RequestException) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return str(exc)
    try:
        body = response.text
    except Exception:
        body = ""
    return f"{exc} {body[:1000]}".strip()
