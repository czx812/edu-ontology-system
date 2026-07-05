"""Adapter for the B-layer ontology generation module.

The project docs define this file as the public B-layer entry point. The real
LLM and ontology-generation logic lives in backend.ai, while this module keeps
the team-facing function signatures stable.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from backend.ai.llm_service import LLMService
from backend.ai.ontology_generator import OntologyGenerator


def build_ontology(clean_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    输入：结构化数据
    输出：本体结构 JSON，包含 classes、properties、relations
    """
    text = _clean_data_to_text(clean_data)
    return OntologyGenerator().generate(text)


def call_llm(prompt: str) -> str:
    """调用大模型并返回原始文本结果。"""
    return LLMService().chat(prompt)


def _clean_data_to_text(clean_data: Dict[str, Any]) -> str:
    if not clean_data:
        return ""

    for key in ("raw_text", "clean_text", "text", "content"):
        value = clean_data.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return json.dumps(clean_data, ensure_ascii=False, indent=2)
