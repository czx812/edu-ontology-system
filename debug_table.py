# 固定路径导入，和test_c逻辑一致
import sys
from pathlib import Path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

# 导入业务节点
from backend.modules.pdf_node import extract_node, clean_node

if __name__ == "__main__":
    test_pdf_list = [
        "JYT1002_教育管理基础信息.pdf",
        "JYT1003_教育行政管理信息.pdf",
        "JYT1006_高等学校管理信息.pdf",
        "JYT1007_教育统计信息.pdf"
    ]

    for target_pdf in test_pdf_list:
        print(f"\n===== 正在处理文件：{target_pdf} =====")
        state = {"file_path": target_pdf}
        state = extract_node(state)
        # 删掉pdf_res，直接读取state["raw_text"]
        print(f"原始文本长度：{len(state['raw_text'])}")
    
        state = clean_node(state)
        clean_res = state["clean_data"]
        table_list = clean_res["tables"]
        print(f"\n【清洗后总表格数量】：{len(table_list)}")

        # 导出全部表格到txt
        txt_name = f"全部表格_{target_pdf.split('.pdf')[0]}.txt"
        with open(txt_name, "w", encoding="utf-8") as f:
            f.write(f"===== {target_pdf} 所有清洗完成表格 =====\n\n")
            for table_idx, one_table in enumerate(table_list, start=1):
                f.write(f"—————— 第{table_idx}张表格 ——————\n")
                for row in one_table:
                    f.write(" | ".join(row) + "\n")
                f.write("\n")
        print(f"全部表格已保存：{txt_name}")