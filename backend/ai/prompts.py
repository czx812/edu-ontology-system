"""Prompt templates for the B layer.

This module only manages prompt text. Semantic matching is kept as a reusable
prompt asset for the D layer; the matching workflow itself does not live here.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict


CANDIDATE_CLASSES = """
EducationResource 教育资源
Person 人员
Student 学生
Teacher 教师
Staff 教职工
School 学校
Campus 校区
Class 班级
Grade 年级
Course 课程
Major 专业
Organization 机构
ContactInfo 联系信息
Enrollment 入学/注册信息
StudentStatus 学籍状态
Exam 考试
Score 成绩
Reward 奖励
Punishment 处分
Graduation 毕业信息
Position 职务
ProfessionalTitle 专业技术职务
Assessment 考核
Training 进修培训
FinanceItem 经费项目
Building 建筑物
Room 房间
Facility 设施
Instrument 仪器设备
Book 图书
Journal 期刊
Laboratory 实验室
Experiment 实验
DataElement 数据元素
DataCatalog 数据类
DataSubcatalog 数据子类
CodeItem 代码项
""".strip()


CANDIDATE_RELATIONS = """
Student -> School belongs_to
Student -> Class belongs_to_class
Class -> Grade belongs_to_grade
Campus -> School campus_of
Course -> Major belongs_to_major
Teacher -> Course teaches
Student -> Course takes_course
Score -> Student score_of_student
Score -> Course score_of_course
Building -> Campus located_in_campus
Room -> Building located_in_building
Instrument -> Room located_in_room
Laboratory -> Room located_in_room
Experiment -> Course experiment_of_course
Book -> School owned_by_school
FinanceItem -> School finance_of_school
Staff -> Organization works_for
Teacher -> School works_for_school
DataElement -> DataSubcatalog belongs_to_subcatalog
DataSubcatalog -> DataCatalog belongs_to_catalog
""".strip()


NOISE_RULES = """
不要把以下内容当成本体元素：目录、前言、范围、规范性引用文件、术语和定义、
本标准依据、中华人民共和国教育行业标准、教育部发布、单独出现的 GB/T 或 JY/T
引用标准标题、--- Table n ---、表头字段、页码、乱码残片、断行残片、单字残片。
表头包括：编号、中文简称、数据项名、解释/举例、值空间、引用编号、类型、长度、约束。
如果 GB/T 或 JY/T 出现在某个数据项 reference/description 中，可以作为证据保留，
但不要单独抽成 class/property。
""".strip()


ENTITY_PROMPT = """
你是“基于大模型智能体的教育本体构建系统”的实体抽取智能体。

任务：
从输入的教育管理标准 clean_data 中抽取实体、数据属性和候选对象关系。
输入可能包含 clean_text、records、tables。请优先理解 records 和 tables，再参考 clean_text。

LLM-first 原则：
你负责识别本体语义。候选类和候选关系只作为参考，不能强制全部输出。
只有输入材料中有证据时，才可以使用候选类或候选关系。

候选类参考：
__CANDIDATE_CLASSES__

候选关系参考：
__CANDIDATE_RELATIONS__

噪声过滤：
__NOISE_RULES__

抽取要求：
1. entities 表示抽象概念类，例如学校、学生、课程、数据子类、代码项。
2. attributes 表示数据属性，例如学校代码、学号、出生日期、联系电话。
3. relations 表示对象关系，例如数据元素属于数据子类、校区属于学校。
4. 每个 class/property/relation 尽量给出 evidence，evidence 必须来自原文或表格。
5. 不要把所有属性都挂到 EducationResource；无法判断 domain 时才使用 EducationResource。
6. 数据项编号如 JCTB010101、JCXX010101、JCXS010101 等通常是属性 name 的重要依据。
7. 如果 records 中有 source_table/source_section，请利用它判断 domain 和关系。
8. relations 可以为空，但不要为了不为空而编造。

输出规则：
1. 只输出合法 JSON 对象，不要输出 Markdown、解释或多余文本。
2. name/type 只能使用字母、数字、下划线；class name 使用 PascalCase，属性和关系使用 snake_case。
3. data_type 只能使用 string、integer、decimal、boolean、date、time、object。
4. 如果没有 evidence，请保留该项但标记 "low_confidence": true。

输出 JSON 结构：
{
  "entities": [
    {
      "name": "<EntityClassName>",
      "label": "<中文实体或概念名>",
      "type": "class",
      "description": "<实体或概念说明>",
      "evidence": "<原文或表格短证据>",
      "parent": "<可选父类>"
    }
  ],
  "attributes": [
    {
      "entity": "<EntityClassName>",
      "name": "<attribute_name>",
      "label": "<中文字段名>",
      "type": "property",
      "data_type": "<string|integer|decimal|boolean|date|time|object>",
      "description": "<字段含义说明>",
      "evidence": "<原文或表格短证据>"
    }
  ],
  "relations": [
    {
      "source": "<SourceEntityClassName>",
      "target": "<TargetEntityClassName>",
      "type": "<relation_type>",
      "label": "<中文关系名>",
      "description": "<关系说明>",
      "evidence": "<原文或表格短证据>",
      "reason": "<推断理由>"
    }
  ]
}

输入 clean_data：
__SOURCE_TEXT__
""".strip()


SEMANTIC_MATCH_PROMPT = """
你是“教育本体构建系统”的语义匹配 Prompt 助手。

任务：
判断不同教育标准中的字段或概念是否语义等价或相似。

规则：
1. 只输出合法 JSON，不要输出 Markdown、解释说明或多余文本。
2. 比较 label、description、domain、data_type、evidence、reference 等信息。
3. score 取值范围为 0 到 1。
4. match_type 可取值：equivalent、similar、related、different。
5. reason 需要简洁说明匹配理由。

输出 JSON 结构：
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


ONTOLOGY_PROMPT = """
你是“基于大模型智能体的教育本体构建系统”的本体生成智能体。

任务：
根据 clean_data、实体抽取 JSON 和候选提示，生成最终 Ontology JSON。

LLM-first 原则：
你负责识别 classes、properties、relations。候选类和候选关系只作为参考，
不能强制全部输出，不能编造输入中没有依据的类或关系。

候选类参考：
__CANDIDATE_CLASSES__

候选关系参考：
__CANDIDATE_RELATIONS__

噪声过滤：
__NOISE_RULES__

本体生成要求：
1. classes 是抽象概念类，不要把目录、前言、引用标准标题、表头、单字残片当成类。
2. properties 是数据属性，必须尽量补全 domain、range、description、evidence。
3. relations 是对象关系，必须有 source、target、type，并给出 evidence 或 reason。
4. 如果第一阶段 relations 为空，请重新根据 source_table、source_section、reference 和业务语义尝试推断关系。
5. 不要为了让 relations 不为空而硬编码或伪造关系。
6. 不要把所有属性都挂到 EducationResource；只有无法判断 domain 时才使用。
7. class 可以包含 parent 字段，用于生成 rdfs:subClassOf。
8. range 只能使用 string、integer、decimal、boolean、date、time。
9. 数据项编号如 JCTB010101、JCXX010101 等应优先作为属性 name，并转为小写。

输出规则：
1. 只输出合法 JSON 对象，不要输出 Markdown、解释或多余文本。
2. 顶层只能包含 classes、properties、relations。
3. name/type 只能使用字母、数字、下划线。
4. 没有 evidence 的项目不要直接删除，但需要标记 "low_confidence": true。

输出 JSON 结构：
{
  "classes": [
    {
      "name": "<ClassName>",
      "label": "<中文类名>",
      "description": "<类说明>",
      "parent": "<可选父类>",
      "evidence": "<原文或表格短证据>"
    }
  ],
  "properties": [
    {
      "name": "<property_name>",
      "label": "<中文属性名>",
      "domain": "<ClassName>",
      "range": "<string|integer|decimal|boolean|date|time>",
      "description": "<属性说明>",
      "evidence": "<原文或表格短证据>"
    }
  ],
  "relations": [
    {
      "source": "<SourceClassName>",
      "target": "<TargetClassName>",
      "type": "<relation_type>",
      "label": "<中文关系名>",
      "description": "<关系说明>",
      "evidence": "<原文或表格短证据>",
      "reason": "<推断理由>"
    }
  ]
}

clean_data：
__SOURCE_TEXT__

实体抽取 JSON：
__ENTITY_JSON__
""".strip()


GLOBAL_RELATION_PROMPT = """
You are the final global relation inference step for an education ontology system.

Task:
Infer object relations across all generated classes, including relations that may
span different batches or source tables. Only output relations that can be
supported by the class names, property domains, labels, evidence, source table
signals, or common education-domain semantics.

Candidate relations:
__CANDIDATE_RELATIONS__

Rules:
1. Output a valid JSON object only. No Markdown and no explanation outside JSON.
2. Output only the top-level key "relations".
3. Do not invent relations just to make the list non-empty.
4. source and target must be existing class names from the ontology context.
5. type must be snake_case.
6. Prefer evidence when present; otherwise provide a concise reason.
7. Do not output datatype properties here.

Output JSON:
{
  "relations": [
    {
      "source": "<SourceClassName>",
      "target": "<TargetClassName>",
      "type": "<relation_type>",
      "label": "<short label>",
      "description": "<relation description>",
      "evidence": "<source evidence if available>",
      "reason": "<why this relation is supported>"
    }
  ]
}

Ontology context:
__ONTOLOGY_CONTEXT__
""".strip()


DEFAULT_MAX_PROMPT_RECORDS = 120
DEFAULT_MAX_PROMPT_TEXT_CHARS = 12000


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _clip_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def _compact_clean_data(data: Any) -> Any:
    if not isinstance(data, dict):
        return _clip_text(data, _env_int("LLM_MAX_PROMPT_TEXT_CHARS", DEFAULT_MAX_PROMPT_TEXT_CHARS))

    max_records = _env_int("LLM_MAX_PROMPT_RECORDS", _env_int("LLM_BATCH_RECORDS", DEFAULT_MAX_PROMPT_RECORDS))
    max_text_chars = _env_int("LLM_MAX_PROMPT_TEXT_CHARS", DEFAULT_MAX_PROMPT_TEXT_CHARS)
    records = data.get("records")
    tables = data.get("tables")

    compact: Dict[str, Any] = {
        "records_count": data.get("records_count", len(records) if isinstance(records, list) else 0),
        "tables_count": data.get("tables_count", len(tables) if isinstance(tables, list) else 0),
    }

    if isinstance(records, list) and records:
        compact["records"] = records[:max_records]
        if len(records) > max_records:
            compact["records_truncated"] = len(records) - max_records
    elif data.get("clean_text"):
        compact["clean_text"] = _clip_text(data.get("clean_text"), max_text_chars)
    elif data.get("raw_text"):
        compact["raw_text"] = _clip_text(data.get("raw_text"), max_text_chars)

    if isinstance(tables, list) and tables and "records" not in compact:
        compact["tables"] = tables[:3]
        if len(tables) > 3:
            compact["tables_truncated"] = len(tables) - 3

    return compact


def _json_text(data: Any) -> str:
    data = _compact_clean_data(data)
    if isinstance(data, str):
        return data.strip()
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_entity_prompt(data: Any) -> str:
    """Build prompt for entity extraction: clean_data/text -> entity JSON."""
    return (
        ENTITY_PROMPT.replace("__SOURCE_TEXT__", _json_text(data))
        .replace("__CANDIDATE_CLASSES__", CANDIDATE_CLASSES)
        .replace("__CANDIDATE_RELATIONS__", CANDIDATE_RELATIONS)
        .replace("__NOISE_RULES__", NOISE_RULES)
    )


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


def build_ontology_prompt(data: Any, entity_json: Dict[str, Any]) -> str:
    """Build prompt for ontology generation: entity JSON -> ontology JSON."""
    payload = json.dumps(entity_json, ensure_ascii=False, indent=2)
    return (
        ONTOLOGY_PROMPT.replace("__SOURCE_TEXT__", _json_text(data))
        .replace("__ENTITY_JSON__", payload)
        .replace("__CANDIDATE_CLASSES__", CANDIDATE_CLASSES)
        .replace("__CANDIDATE_RELATIONS__", CANDIDATE_RELATIONS)
        .replace("__NOISE_RULES__", NOISE_RULES)
    )


def build_global_relation_prompt(ontology: Dict[str, Any], entity_json: Dict[str, Any]) -> str:
    """Build prompt for final cross-batch relation inference."""
    context = _global_relation_context(ontology, entity_json)
    payload = json.dumps(context, ensure_ascii=False, indent=2)
    return (
        GLOBAL_RELATION_PROMPT.replace("__ONTOLOGY_CONTEXT__", payload)
        .replace("__CANDIDATE_RELATIONS__", CANDIDATE_RELATIONS)
    )


def _global_relation_context(ontology: Dict[str, Any], entity_json: Dict[str, Any]) -> Dict[str, Any]:
    max_properties = _env_int("LLM_GLOBAL_RELATION_PROPERTIES", 400)
    classes = ontology.get("classes", []) if isinstance(ontology, dict) else []
    properties = ontology.get("properties", []) if isinstance(ontology, dict) else []
    entity_relations = entity_json.get("relations", []) if isinstance(entity_json, dict) else []

    return {
        "classes": [
            {
                "name": item.get("name"),
                "label": item.get("label"),
                "parent": item.get("parent", ""),
                "description": item.get("description", ""),
                "evidence": item.get("evidence", ""),
            }
            for item in classes
            if isinstance(item, dict)
        ],
        "properties": [
            {
                "name": item.get("name"),
                "label": item.get("label"),
                "domain": item.get("domain"),
                "range": item.get("range"),
                "description": item.get("description", ""),
                "evidence": item.get("evidence", ""),
            }
            for item in properties[:max_properties]
            if isinstance(item, dict)
        ],
        "properties_total": len(properties) if isinstance(properties, list) else 0,
        "properties_truncated": max(0, len(properties) - max_properties) if isinstance(properties, list) else 0,
        "candidate_relations_from_batches": entity_relations,
    }


def build_prompt(data: Dict[str, Any]) -> str:
    """Compatibility helper required by older module interface documents."""
    return build_ontology_prompt(data, data.get("entity_json", {}))


def build_entity_extraction_prompt(text: str) -> str:
    """Backward-compatible alias."""
    return build_entity_prompt(text)


def build_ontology_generation_prompt(text: str, entity_json: Dict[str, Any]) -> str:
    """Backward-compatible alias."""
    return build_ontology_prompt(text, entity_json)
