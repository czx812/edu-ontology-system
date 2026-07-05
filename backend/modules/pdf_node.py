from backend.modules.pdf_parser import extract_pdf
from backend.modules.data_cleaner import clean_data
from backend.utils.file_utils import logger

def extract_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """C规范提取节点：流式state透传"""
    file_path = state.get("file_path", "")
    if not file_path:
        logger.warning("state缺失file_path，跳过提取")
        return state
    try:
        raw_str = extract_pdf(file_path)
        state["raw_text"] = raw_str
        state["pdf_name"] = file_path
    except Exception as e:
        logger.error(f"提取PDF失败 {file_path}: {str(e)}")
        state["raw_text"] = ""
    return state

def clean_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """C规范清洗节点"""
    raw_text = state.get("raw_text", "")
    if not raw_text:
        state["clean_data"] = {"raw_text": "", "tables": []}
        return state
    try:
        res = clean_data(raw_text)
        state["clean_data"] = res
        # JYT1002专属71张表校验
        pdf_name = state.get("pdf_name", "")
        if "JYT1002" in pdf_name:
            table_cnt = len(res["tables"])
            if table_cnt != 71:
                logger.warning(f"JYT1002校验异常，当前{table_cnt}张，标准要求71张！")
            else:
                logger.success("JYT1002表格校验通过，完整71张")
    except Exception as e:
        logger.error(f"清洗失败: {str(e)}")
        state["clean_data"] = {"raw_text": raw_text, "tables": []}
    return state