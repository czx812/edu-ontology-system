import re
from typing import Dict, List, Any
from backend.utils.file_utils import logger

# 修复：补齐9列表头
STANDARD_HEAD_FULL = [
    "编号", "数据项名", "中文简称", "类型", "长度",
    "约束", "值空间", "解释/举例", "引用编号"
]
CELL_SEP = "⦙"
TABLE_HEAD_MARK = "===== JYT标准所有清洗完成表格 =====\n"

def clean_data(raw_text: str) -> Dict[str, Any]:
    """
    C规范清洗函数：分割、过滤、去重标准数据表
    """
    # 基础文本降噪
    clean_txt = re.sub(r"\s{3,}", " ", raw_text)
    clean_txt = re.sub(r"\n{3,}", "\n\n", clean_txt)
    tables_result = []

    split_parts = clean_txt.split(TABLE_HEAD_MARK)
    if len(split_parts) <= 1:
        return {"raw_text": clean_txt, "tables": []}
    table_content_block = split_parts[1]

    # 分割每张表
    table_sep_pattern = re.compile(r"—————— 第\d+张标准数据表 ——————\n")
    single_table_blocks = table_sep_pattern.split(table_content_block)

    for block in single_table_blocks[1:]:
        block_lines = [l.strip() for l in block.split("\n") if l.strip()]
        tbl_data = []
        for line in block_lines:
            row_cells = line.split(CELL_SEP)
            tbl_data.append(row_cells)
        # 校验表合法性：至少3行+9列表头
        if len(tbl_data) < 3 or len(tbl_data[0]) != 9:
            continue
        header_check = [c.strip() for c in tbl_data[0]]
        if header_check != STANDARD_HEAD_FULL:
            continue
        # 过滤全空行
        filter_tbl = [row for row in tbl_data if any(x.strip() for x in row)]
        tables_result.append(filter_tbl)

    # 去重优化：使用MD5指纹
    final_tables = []
    seen_fp = set()
    for tbl in tables_result:
        sample = "||".join([row[0] for row in tbl[1:8]])
        fp = hash(sample)  # 轻量化哈希
        if fp not in seen_fp:
            seen_fp.add(fp)
            final_tables.append(tbl)

    logger.info(f"文本清洗完成，有效标准表数量：{len(final_tables)}")
    return {
        "raw_text": clean_txt,
        "tables": final_tables
    }