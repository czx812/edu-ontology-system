"""Prompt templates for ontology construction."""

from __future__ import annotations

import json
from typing import Any, Dict


ENTITY_PROMPT = """
你是教育领域本体构建助手。请从输入文本中抽取实体、属性和关系。

只输出一个合法 JSON 对象，不要输出 Markdown，不要解释。
如果内容很多，优先保留表名、字段名、代码项、统计指标、管理对象等核心信息。
为了避免输出过长，请控制规模：entities 不超过 80 个，attributes 不超过 220 个，relations 不超过 100 个。
输出前必须自检 JSON 是否完整闭合。

JSON 格式：
{
  "entities": [
    {
      "name": "EntityName",
      "label": "中文实体名",
      "type": "class|standard|document|organization|person|course|table|indicator|enum|other",
      "description": "含义说明",
      "evidence": "原文短证据"
    }
  ],
  "attributes": [
    {
      "entity": "EntityName",
      "name": "attribute_name",
      "label": "中文字段名",
      "data_type": "string|integer|float|date|boolean|object",
      "description": "字段含义说明",
      "evidence": "原文短证据"
    }
  ],
  "relations": [
    {
      "source": "SourceEntityName",
      "target": "TargetEntityName",
      "type": "relation_type",
      "label": "中文关系名",
      "description": "关系说明",
      "evidence": "原文短证据"
    }
  ]
}

命名规则：
1. name 使用英文 PascalCase 或 snake_case。
2. label 保留中文原词。
3. 不确定所属实体的属性，entity 使用 EducationResource。
4. 只合并语义完全重复的项，不要过度合并相似字段。

输入文本：
__SOURCE_TEXT__
""".strip()


SEMANTIC_MATCH_PROMPT = """
请判断 source_items 与 target_items 中字段或概念的语义匹配关系。
只输出合法 JSON，不要输出 Markdown 或解释。

{
  "matches": [
    {
      "source": "source_name",
      "target": "target_name",
      "source_label": "源字段中文名",
      "target_label": "目标字段中文名",
      "match_type": "equivalent|similar|related|different",
      "score": 0.0,
      "reason": "匹配理由"
    }
  ]
}

Source items:
__SOURCE_ITEMS__

Target items:
__TARGET_ITEMS__
""".strip()


ONTOLOGY_PROMPT = """
请根据实体抽取 JSON 生成本体 JSON。
只输出合法 JSON，不要输出 Markdown 或解释。

{
  "classes": [
    {"name": "ClassName", "label": "中文类名", "description": "类说明"}
  ],
  "properties": [
    {"name": "property_name", "label": "中文属性名", "domain": "ClassName", "range": "string", "description": "属性说明"}
  ],
  "relations": [
    {"source": "SourceClass", "target": "TargetClass", "type": "relation_type", "label": "中文关系名", "description": "关系说明"}
  ]
}

原始文本：
__SOURCE_TEXT__

实体抽取 JSON：
__ENTITY_JSON__
""".strip()


def build_entity_prompt(text: str) -> str:
    """Build prompt for entity extraction: source text -> entity JSON."""
    return ENTITY_PROMPT.replace("__SOURCE_TEXT__", text.strip())


def build_semantic_match_prompt(
    source_items: Dict[str, Any],
    target_items: Dict[str, Any],
) -> str:
    """Build prompt for semantic matching."""
    source_payload = json.dumps(source_items, ensure_ascii=False, indent=2)
    target_payload = json.dumps(target_items, ensure_ascii=False, indent=2)
    return (
        SEMANTIC_MATCH_PROMPT.replace("__SOURCE_ITEMS__", source_payload)
        .replace("__TARGET_ITEMS__", target_payload)
    )


def build_ontology_prompt(text: str, entity_json: Dict[str, Any]) -> str:
    """Build prompt for ontology generation: entity JSON -> ontology JSON."""
    payload = json.dumps(entity_json, ensure_ascii=False, indent=2)
    return (
        ONTOLOGY_PROMPT.replace("__SOURCE_TEXT__", text.strip())
        .replace("__ENTITY_JSON__", payload)
    )


def build_entity_extraction_prompt(text: str) -> str:
    """Backward-compatible alias."""
    return build_entity_prompt(text)


def build_ontology_generation_prompt(text: str, entity_json: Dict[str, Any]) -> str:
    """Backward-compatible alias."""
    return build_ontology_prompt(text, entity_json)
