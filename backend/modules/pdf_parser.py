import re
import os
import subprocess
from io import BytesIO
from pathlib import Path
import pdfplumber
import camelot
from typing import List, Set, Dict, Any
from utils.file_utils import read_file_bytes, calc_md5, safe_remove, logger

# ====================== 全局标准常量（统一配置） ======================
# JYT标准9列表头（补齐引用编号）
STANDARD_HEAD_FULL = [
    "编号", "数据项名", "中文简称", "类型", "长度",
    "约束", "值空间", "解释/举例", "引用编号"
]
CELL_SEP = "⦙"
TABLE_HEAD_MARK = "===== JYT标准所有清洗完成表格 =====\n"
TABLE_BLOCK_TPL = "—————— 第{}张标准数据表 ——————\n"
CODE_PREFIX = ("JC", "JCTB", "JCXX", "JCXS", "JCJG", "JCBX")
# pdfplumber表格提取配置
SETTINGS_LINES = {
    "vertical_strategy": "lines", "horizontal_strategy": "lines",
    "snap_tolerance": 12, "join_tolerance": 10, "edge_min_length": 2,
    "text_tolerance": 6, "intersection_x_tolerance": 6, "intersection_y_tolerance": 6
}
SETTINGS_TEXT = {
    "vertical_strategy": "text", "horizontal_strategy": "text",
    "snap_tolerance": 8, "intersection_x_tolerance": 8, "intersection_y_tolerance": 8,
    "text_x_tolerance": 5, "text_y_tolerance": 5
}
# 可配置mutool路径，适配多系统
MUTOOL_EXE = r"D:\tools\mupdf\mutool.exe"
TEMP_PDF_NAME = ".tmp_fix_pdf.pdf"

# ===================== 工具函数 ======================
def merge_cell_newline(raw_table: List[List[Any]]) -> List[List[str]]:
    """单元格清洗：合并空白、换行"""
    clean_table = []
    for row in raw_table:
        new_row = []
        for cell in row:
            cell = cell if cell is not None else ""
            cell = re.sub(r"\s+", " ", str(cell).strip())
            new_row.append(cell)
        clean_table.append(new_row)
    return clean_table

def is_legal_standard_table(table: List[List[str]]) -> bool:
    """校验是否是合法JYT标准9列表"""
    if len(table) < 3:
        return False
    header = [c.strip() for c in table[0] if c.strip()]
    if header != STANDARD_HEAD_FULL:
        return False
    first_code = table[1][0].strip()
    # 放宽编码长度限制，兼容标准内取用短编码
    if not any(first_code.startswith(prefix) for prefix in CODE_PREFIX):
        return False
    return True

def get_table_finger(table: List[List[str]]) -> str:
    """优化指纹：表头+前8行编码MD5，避免误删"""
    sample_rows = "||".join([row[0] for row in table[1:8]])
    raw_key = f"{STANDARD_HEAD_FULL}|{sample_rows}"
    return calc_md5(raw_key)

def format_standard_table(raw_table: List[List[str]]) -> List[List[str]]:
    """规整9列表，修复错位，抛弃不稳定正则分割逻辑"""
    fixed = [STANDARD_HEAD_FULL.copy()]
    for row in raw_table[1:]:
        row_clean = [x.strip() if x else "" for x in row]
        # 不足9列补空，超过截断，不做复杂文本拆分
        standard_row = [""] * 9
        fill_len = min(len(row_clean), 9)
        for i in range(fill_len):
            standard_row[i] = row_clean[i]
        # 过滤全空行
        if any(cell != "" for cell in standard_row):
            fixed.append(standard_row)
    return fixed

def extract_page_tables(page, all_seen: Set[str]) -> List[List[List[str]]]:
    """单页提取表格，修复tbl_obj笔误，删除无用temp_pdf_path参数"""
    page_tables = []
    tbl_lines = page.find_tables(table_settings=SETTINGS_LINES)
    tbl_text = page.find_tables(table_settings=SETTINGS_TEXT)
    all_raw_tbl = tbl_lines + tbl_text

    for tbl_obj in all_raw_tbl:
        try:
            raw = tbl_obj.extract()  # 修复变量名tbl_obj
            tbl_merge = merge_cell_newline(raw)
            if not is_legal_standard_table(tbl_merge):
                continue
            tbl_fixed = format_standard_table(tbl_merge)
            fp = get_table_finger(tbl_fixed)
            if fp not in all_seen:
                all_seen.add(fp)
                page_tables.append(tbl_fixed)
        except Exception as e:
            logger.warning(f"单页表格解析失败，跳过: {str(e)}")
    return page_tables

def extract_camelot_tables(pdf_path: str, all_seen: Set[str]) -> List[List[List[str]]]:
    """camelot兜底提取，增加依赖提示"""
    camelot_tables = []
    try:
        lat_tbls = camelot.read_pdf(pdf_path, flavor="lattice")
        str_tbls = camelot.read_pdf(pdf_path, flavor="stream")
        for ct in lat_tbls + str_tbls:
            df_arr = ct.df.values.tolist()
            tbl_merge = merge_cell_newline(df_arr)
            if not is_legal_standard_table(tbl_merge):
                continue
            tbl_fixed = format_standard_table(tbl_merge)
            fp = get_table_finger(tbl_fixed)
            if fp not in all_seen:
                all_seen.add(fp)
                camelot_tables.append(tbl_fixed)
    except ImportError:
        logger.error("未安装camelot，执行 pip install camelot-py[cv] 并安装Ghostscript")
    except Exception as e:
        logger.warning(f"Camelot提取异常: {str(e)}")
    return camelot

# ====================== 对外统一接口（上层不变） ======================
def extract_pdf(file_path: str) -> str:
    """
    C规范PDF提取接口
    :param file_path: PDF路径
    :return: 拼接全文+分隔表格的结构化文本
    """
    raw_full_text = ""
    valid_all_tables = []
    seen_finger_set: Set[str] = set()
    fix_pdf_path = file_path
    use_temp = False

    # 步骤1 mutool修复损坏PDF
    try:
        mut_path = Path(MUTOOL_EXE)
        if mut_path.exists():
            ret = subprocess.run(
                [MUTOOL_EXE, "clean", file_path, TEMP_PDF_NAME],
                capture_output=True, text=True
            )
            if ret.returncode == 0:
                fix_pdf_path = TEMP_PDF_NAME
                use_temp = True
    except Exception as e:
        logger.info(f"mutool不可用，使用原文件: {str(e)}")

    # 步骤2 读取二进制，只打开一次pdf
    pdf_bytes = read_file_bytes(file_path)
    pdf_stream = BytesIO(pdf_bytes)

    # 提取纯文本
    with pdfplumber.open(pdf_stream) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            page_txt = page.extract_text() or ""
            raw_full_text += f"\n【第{page_idx}页】\n{page_txt}\n\n"

    # 重置流，提取表格（仅打开一次）
    pdf_stream.seek(0)
    with pdfplumber.open(pdf_stream) as pdf:
        for page in pdf.pages:
            page_tbls = extract_page_tables(page, seen_finger_set)
            valid_all_tables.extend(page_tbls)

    # camelot兜底
    cam_tables = extract_camelot_tables(fix_pdf_path, seen_finger_set)
    valid_all_tables.extend(cam_tables)

    # 拼接标准化输出文本（兼容clean_data分割逻辑）
    raw_full_text += TABLE_HEAD_MARK
    for idx, table in enumerate(valid_all_tables, 1):
        raw_full_text += TABLE_BLOCK_TPL.format(idx)
        for row in table:
            raw_full_text += CELL_SEP.join(row) + "\n"
        raw_full_text += "\n"

    # 清理临时文件
    if use_temp:
        safe_remove(TEMP_PDF_NAME)
    logger.success(f"PDF {file_path} 提取完成，识别标准表{len(valid_all_tables)}张")
    return raw_full_text.strip()