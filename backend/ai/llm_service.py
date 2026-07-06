"""LLM API client for the B layer."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional
from urllib import error, request


DEFAULT_LLM_BASE_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_LLM_MODEL = "deepseek-chat"


class LLMService:
    """OpenAI-compatible chat completion client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120,
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(
        self,
        prompt: str,
        temperature: float = 0.2,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not configured.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.base_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM request failed: {exc.code} {detail}") from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(
                "LLM network request failed. Check LLM_BASE_URL, network/proxy, "
                f"and model settings. Detail: {exc}"
            ) from exc

        return result["choices"][0]["message"]["content"]

    def chat_json(self, prompt: str, temperature: float = 0.1) -> Dict[str, Any]:
        try:
            content = self.chat(prompt, temperature=temperature, json_mode=True)
        except RuntimeError as exc:
            if "response_format" not in str(exc):
                raise
            content = self.chat(prompt, temperature=temperature, json_mode=False)

        try:
            return extract_json_object(content)
        except ValueError as exc:
            repair_prompt = (
                "下面是一段模型输出的、不完整或不合法的 JSON。"
                "请只根据已有内容修复为一个合法 JSON 对象。"
                "如果内容被截断，不要补造新事实，只保留已经完整出现的项目，并正确闭合数组和对象。"
                "不要输出 Markdown 或解释。\n\n"
                f"{content[:30000]}"
            )
            repaired = self.chat(repair_prompt, temperature=0.0, json_mode=True)
            try:
                return extract_json_object(repaired)
            except ValueError:
                raise ValueError(f"{exc} Raw LLM output prefix: {content[:500]}") from exc


def extract_json_object(content: str) -> Dict[str, Any]:
    """Extract a JSON object from raw LLM output."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start < 0:
        raise ValueError("LLM output does not contain a JSON object.")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    data = json.loads(text[start : index + 1])
                    if not isinstance(data, dict):
                        raise ValueError("Extracted JSON is not an object.")
                    return data

    raise ValueError("LLM output contains incomplete JSON.")

