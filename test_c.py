import sys
from pathlib import Path
# 项目根目录加入环境变量
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))
from backend.modules.pdf_node import extract_node, clean_node
from backend.utils.file_utils import logger

if __name__ == "__main__":
    # 待解析4份PDF
    test_pdf_list = [
        "JYT1002_教育管理基础信息.pdf",
        "JYT1003_教育行政管理信息.pdf",
        "JYT1006_高等学校管理信息.pdf",
        "JYT1007_教育统计信息.pdf"
    ]

    for pdf_path in test_pdf_list:
        print(f"\n========== 开始处理 {pdf_path} ==========")
        state = {"file_path": pdf_path}
        # 1 提取节点
        state = extract_node(state)
        raw_text = state.get("raw_text", "")
        print(f"原始文本长度：{len(raw_text)}")
        if not raw_text:
            print("无提取内容，跳过清洗")
            continue
        # 2 清洗节点
        state = clean_node(state)
        clean_res = state["clean_data"]
        table_count = len(clean_res.get("tables", []))
        print(f"清洗后标准数据表总数：{table_count}")

        # 导出表格文本
        out_txt = f"输出表格_{Path(pdf_path).stem}.txt"
        with open(out_txt, "w", encoding="utf-8") as f:
            f.write(f"文件：{pdf_path} 解析结果\n\n")
            for idx, tbl in enumerate(clean_res["tables"], 1):
                f.write(f"===== 第{idx}张数据表 =====\n")
                for row in tbl:
                    f.write(" | ".join(row) + "\n")
                f.write("\n")
        print(f"表格文件已输出：{out_txt}")