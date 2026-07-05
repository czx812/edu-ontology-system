from typing import Any, Dict, List


FIELD_MAP = {
    "编号": "id",
    "数据项名": "item_name",
    "数据项 名": "item_name",
    "中文简称": "cn_name",
    "中文名称": "cn_name",
    "类型": "data_type",
    "类 型": "data_type",
    "长度": "length",
    "长 度": "length",
    "约束": "constraint",
    "约 束": "constraint",
    "值空间": "value_space",
    "值 空 间": "value_space",
    "解释/举例": "description",
    "解释": "description",
    "举例": "description",
    "引用编号": "reference",
    "引用 编号": "reference",
}


def _normalize_key(key: str) -> str:
    key = str(key).strip().replace("\n", "")
    return FIELD_MAP.get(key, key)


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    new_row = {}

    for key, value in row.items():
        std_key = _normalize_key(key)
        if isinstance(value, str):
            value = value.strip()
        new_row[std_key] = value

    return {
        "id": new_row.get("id", ""),
        "item_name": new_row.get("item_name", ""),
        "cn_name": new_row.get("cn_name", ""),
        "data_type": new_row.get("data_type", ""),
        "length": new_row.get("length", ""),
        "constraint": new_row.get("constraint", ""),
        "value_space": new_row.get("value_space", ""),
        "description": new_row.get("description", ""),
        "reference": new_row.get("reference", ""),
    }


def match_schema(clean_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    输入：C模块清洗后的数据
    输出：字段统一后的标准数据

    期望 C 模块给你的 clean_data 大概长这样：
    {
        "raw_text": "...",
        "tables": [
            {
                "title": "表2 学校基本数据子类表",
                "rows": [
                    {"编号": "...", "数据项名": "...", "中文简称": "..."}
                ]
            }
        ]
    }
    """

    tables = clean_data.get("tables", [])
    records: List[Dict[str, Any]] = []

    for table in tables:
        table_title = table.get("title", "")
        rows = table.get("rows", [])

        for row in rows:
            normalized = _normalize_row(row)
            normalized["source_table"] = table_title

            if normalized["id"] or normalized["cn_name"] or normalized["item_name"]:
                records.append(normalized)

    return {
        "source_file": clean_data.get("source_file", ""),
        "raw_text": clean_data.get("raw_text", ""),
        "tables_count": len(tables),
        "records": records,
    }