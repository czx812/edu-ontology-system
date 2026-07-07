"""Prompt templates for ontology construction."""

from __future__ import annotations

import json
from typing import Any, Dict


ENTITY_PROMPT = """
你是教育领域语义本体构建助手。请从输入文本中抽取概念类、数据属性和对象关系。

只输出一个合法 JSON 对象，不要输出 Markdown，不要解释。
如果内容很多，优先保留表名、字段名、代码项、统计指标、管理对象等核心信息。
为了避免输出过长，请控制规模：entities 不超过 80 个，attributes 不超过 220 个，relations 不超过 100 个。
输出前必须自检 JSON 是否完整闭合。

核心语义规则：
1. 必须判断每个字段的语义类型：class / property / relation。
2. 不允许把所有输出默认成 class。
3. JCTB 数据项、电话、邮箱、邮政编码、编号、姓名、地址、日期等字段必须标注为 property。
4. 学生、学校、教师、课程、联系信息等抽象概念可以标注为 class。
5. 学生属于学校、学生选修课程、教师任教课程等对象间连接必须标注为 relation。
6. attributes 中的每个数据项必须包含 type 或 semantic_type = "property"。

JSON 格式：
{
  "entities": [
    {
      "name": "Student",
      "label": "学生",
      "type": "class",
      "semantic_type": "class",
      "description": "含义说明",
      "evidence": "原文短证据"
    }
  ],
  "attributes": [
    {
      "entity": "Student",
      "name": "phone",
      "label": "电话",
      "type": "property",
      "semantic_type": "property",
      "data_type": "string|integer|float|date|boolean|object",
      "description": "字段含义说明",
      "evidence": "原文短证据"
    }
  ],
  "relations": [
    {
      "source": "Student",
      "target": "School",
      "type": "belongs_to",
      "semantic_type": "relation",
      "label": "属于",
      "description": "关系说明",
      "evidence": "原文短证据"
    }
  ]
}

命名规则：
1. class name 使用英文 PascalCase，如 Student、School、ContactInfo。
2. property 和 relation name 使用英文 snake_case，如 phone、email、belongs_to。
3. label 保留中文原词。
4. 不确定所属实体的属性，entity 使用 EducationResource。
5. 只合并语义完全重复的项，不要过度合并相似字段。

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
请根据语义分类 JSON 生成本体 JSON。
只输出合法 JSON，不要输出 Markdown 或解释。

要求：
1. classes 只能包含抽象概念类，不能包含电话、邮箱、邮政编码、编号等字段。
2. properties 只能包含数据属性，必须设置 domain 和 range。
3. relations 只能包含对象关系，必须设置 source、target 和 type。

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


def build_semantic_match_prompt(source_items: Dict[str, Any], target_items: Dict[str, Any]) -> str:
    """Build prompt for semantic matching."""
    source_payload = json.dumps(source_items, ensure_ascii=False, indent=2)
    target_payload = json.dumps(target_items, ensure_ascii=False, indent=2)
    return SEMANTIC_MATCH_PROMPT.replace("__SOURCE_ITEMS__", source_payload).replace("__TARGET_ITEMS__", target_payload)


def build_ontology_prompt(text: str, entity_json: Dict[str, Any]) -> str:
    """Build prompt for ontology generation: entity JSON -> ontology JSON."""
    payload = json.dumps(entity_json, ensure_ascii=False, indent=2)
    return ONTOLOGY_PROMPT.replace("__SOURCE_TEXT__", text.strip()).replace("__ENTITY_JSON__", payload)


def build_entity_extraction_prompt(text: str) -> str:
    """Backward-compatible alias."""
    return build_entity_prompt(text)


def build_ontology_generation_prompt(text: str, entity_json: Dict[str, Any]) -> str:
    """Backward-compatible alias."""
    return build_ontology_prompt(text, entity_json)
