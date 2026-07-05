from mock_data import get_mock_state
from schema_matcher import schema_matcher
from ontology_aligner import ontology_aligner
from owl_generator import generate_owl

print("\n🚀 D模块开始运行...\n")

# 1. 获取数据
state = get_mock_state()

# 2. schema匹配
state = schema_matcher(state)

# 3. ontology优化
state = ontology_aligner(state)

# 4. OWL生成
state = generate_owl(state)

print("\n🎉 全部完成！")
print("最终OWL文件：", state["owl_file"])