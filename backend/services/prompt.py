"""Compatibility prompt helpers."""

from __future__ import annotations

from typing import Any, Dict

from backend.ai.prompts import (
    build_entity_prompt,
    build_ontology_prompt,
    build_prompt,
    build_semantic_match_prompt,
)

__all__ = [
    "build_prompt",
    "build_entity_prompt",
    "build_ontology_prompt",
    "build_semantic_match_prompt",
]
