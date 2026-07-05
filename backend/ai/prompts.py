"""Prompt templates for the B layer.

This module only manages prompt text. The semantic matching prompt is kept here
as a reusable prompt asset for the D layer, while the matching workflow itself
belongs outside the B layer.
"""

from __future__ import annotations

import json
from typing import Any, Dict


# 实体抽取 Prompt
ENTITY_PROMPT = """
你是“教育本体构建系统”的实体抽取智能体。

任务：
请从输入的教育标准文本中尽可能完整地抽取结构化语义信息。

需要识别：
1. entities：教育领域实体/概念，例如主体对象、组织机构、业务对象、标准文档、数据表、统计指标。
2. attributes：实体属性/字段，例如编号、名称、代码、日期、类型、状态、说明、枚举值、统计值。
3. relations：实体之间的语义关系，例如所属、包含、管理、开设、统计、引用、对应。

完整性要求：
1. 不要只抽取示例字段，要尽可能覆盖原文中出现的所有表名、字段名、代码项、枚举项、指标名、统计项。
2. 如果输入文本来自表格，请逐行理解字段含义；每个字段都应尽量出现在 attributes 中。
3. 如果字段所属实体不明确，请根据上下文推断一个最合理的 entity；仍不确定时使用 EducationResource。
4. 不要因为字段相似就直接丢弃；只有语义完全重复时才合并。
5. 对不确定但有价值的概念也要保留，并在 description 中说明其可能含义。
6. 输出前自检：entities、attributes、relations 是否覆盖了原文主要概念和字段。

规则：
1. 只输出 JSON，不要输出 Markdown、解释说明或多余文本。
2. name 使用英文 snake_case 或 PascalCase。
3. label 保留中文原词。
4. type 可取值：class、field、standard、document、organization、person、course、table、indicator、enum、other。
5. data_type 可取值：string、integer、float、date、boolean、object。
6. evidence 填写来自原文的短证据。
7. 如果无法确定关系，relations 返回空数组。

输出 JSON 格式，注意尖括号内容是占位说明，不是固定结果：
{
  "entities": [
    {
      "name": "<EntityClassName>",
      "label": "<中文实体或概念名>",
      "type": "<class|standard|document|organization|person|course|table|indicator|enum|other>",
      "description": "<实体或概念说明>",
      "evidence": "<原文证据>"
    }
  ],
  "attributes": [
    {
      "entity": "<EntityClassName>",
      "name": "<attribute_name>",
      "label": "<中文字段名>",
      "data_type": "<string|integer|float|date|boolean|object>",
      "description": "<字段含义说明>",
      "evidence": "<原文证据>"
    }
  ],
  "relations": [
    {
      "source": "<SourceEntityClassName>",
      "target": "<TargetEntityClassName>",
      "type": "<relation_type>",
      "label": "<中文关系名>",
      "description": "<关系说明>",
      "evidence": "<原文证据>"
    }
  ]
}

输入文本：
__SOURCE_TEXT__
""".strip()


# 语义匹配 Prompt，供 D 层调用
SEMANTIC_MATCH_PROMPT = """
你是“教育本体构建系统”的语义匹配 Prompt 助手。

任务：
判断不同教育标准中的字段或概念是否语义等价或相似。

规则：
1. 只输出 JSON，不要输出 Markdown、解释说明或多余文本。
2. 比较 label、description、domain、data_type、evidence 等信息。
3. score 取值范围为 0 到 1。
4. match_type 可取值：equivalent、similar、related、different。
5. reason 需要简洁说明匹配理由。

输出 JSON 格式，注意尖括号内容是占位说明，不是固定结果：
{
  "matches": [
    {
      "source": "<source_name>",
      "target": "<target_name>",
      "source_label": "<源字段中文名>",
      "target_label": "<目标字段中文名>",
      "match_type": "<equivalent|similar|related|different>",
      "score": 0.0,
      "reason": "<匹配理由>"
    }
  ]
}

Source items:
__SOURCE_ITEMS__

Target items:
__TARGET_ITEMS__
""".strip()


# 本体生成 Prompt
ONTOLOGY_PROMPT = """
你是“教育本体构建系统”的本体生成智能体。

任务：
请根据实体抽取 JSON，生成尽可能完整的最终 Ontology JSON。

目标：
把 entities、attributes、relations 整理为教育领域本体结构。

完整性要求：
1. classes 应尽可能覆盖 entity extraction JSON 中所有有价值的 entities。
2. properties 应尽可能覆盖 entity extraction JSON 中所有 attributes。
3. relations 应尽可能覆盖 entity extraction JSON 中所有明确或可合理推断的 relations。
4. 每个 property 必须尽量补全 domain 和 range。
5. 不要遗漏代码项、枚举项、统计指标、表格字段；无法确定时也要保留为属性或类。
6. 合并重复项，但不要把语义相近但不完全相同的字段错误合并。
7. 输出前自检：classes/properties/relations 是否覆盖 entity extraction JSON 的主要内容。

规则：
1. 只输出 JSON，不要输出 Markdown、解释说明或多余文本。
2. 顶层只能包含 classes、properties、relations 三个字段。
3. classes 表示本体类。
4. properties 表示类的数据属性。
5. relations 表示类与类之间的对象关系。
6. name 使用英文 snake_case 或 PascalCase，label 保留中文原词。

输出 JSON 格式，注意尖括号内容是占位说明，不是固定结果：
{
  "classes": [
    {
      "name": "<ClassName>",
      "label": "<中文类名>",
      "description": "<类说明>"
    }
  ],
  "properties": [
    {
      "name": "<property_name>",
      "label": "<中文属性名>",
      "domain": "<ClassName>",
      "range": "<string|integer|float|date|boolean|object>",
      "description": "<属性说明>"
    }
  ],
  "relations": [
    {
      "source": "<SourceClassName>",
      "target": "<TargetClassName>",
      "type": "<relation_type>",
      "label": "<中文关系名>",
      "description": "<关系说明>"
    }
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
    """Build prompt for semantic matching, which is called by the D layer."""
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
