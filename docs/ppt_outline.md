# 基于大模型智能体的教育本体构建系统 —— 答辩 PPT 大纲

> 生成依据：已阅读当前项目代码、`frontend/README.md`、`docs/`、实训报告、后端数据目录与导出结果；当前工程未发现 `diagrams` 目录，因此另生成 `docs/diagrams.md`。

## 第1页：封面
- 题目：基于大模型智能体的教育本体构建系统
- 小组成员：程梓轩、杨慧、孙艺凯、陈娟
- 指导老师：王颖
- 日期：2026年7月9日
- 风格：蓝白科技风，教育信息化主题

## 第2页：项目背景
- 教育数据来源复杂，教育管理、统计和高校标准文档并存
- PDF 文档与表格结构不统一，字段命名和约束表达差异明显
- 人工构建本体效率低，准确性依赖专家经验与反复校对
- 引入大模型智能体，提升教育本体构建的自动化和语义理解能力

## 第3页：项目目标
- 支持教育类 PDF 上传与批量上传
- 自动解析文本和表格，清洗为结构化记录
- 完成字段标准化、候选领域识别和本体草稿生成
- 通过 LLM 进行语义增强，输出类、属性、关系
- 支持本体对齐、数据溯源、日志审计和 OWL 导出

## 第4页：系统总体架构
- Vue 前端、FastAPI 后端、PDF 解析、数据清洗、LLM 语义增强、Schema Matcher、Ontology Aligner、OWL Generator、SQLite/日志/文件存储、OWL 导出结果。

## 第5页：系统功能模块
- 用户登录注册、PDF 上传、本体生成、结果展示、OWL 导出、数据溯源、日志审计、管理员用户管理。

## 第6页：核心业务流程
- 用户上传 PDF → PDF 解析 → 数据清洗 → Schema 匹配 → 规则草稿 → LLM 语义增强 → 本体对齐 → 溯源 → OWL 生成 → 前端展示/导出。

## 第7页：PDF 文档解析与清洗 DFD
- 外部实体：用户；加工：PDF 文件接收、文本/表格提取、数据清洗标准化；存储：临时文件缓存池；输出：clean_data。

## 第8页：大模型智能体设计
- OpenAI 兼容 LLMService，支持 base_url、model、api_key 配置
- Prompt 要求 strict JSON 输出，禁止 Markdown 包裹
- 不固定 Student/Teacher/School 等类名，由记录语义和候选领域动态生成
- 规则草稿保障基础可用，大模型负责对象关系与语义增强
- LLM 失败或超时时保留规则兜底结果，避免流程整体中断
- 重点：输出重点：classes / datatype_properties / object_properties / relations

## 第9页：本体构建数据结构
- 展示 ontology JSON：classes、datatype_properties/properties、object_properties、relations；解释 class/property/relation/domain/range/label。

## 第10页：Schema Matcher 设计
- 字段标准化和语义匹配：课程名称/课程名→course_name，学校名称/学校名→school_name，专业代码/专业编号→major_code；代码中实际标准化为 id、item_name、cn_name、data_type、length、constraint、value_space、description、reference 等统一字段。

## 第11页：Ontology Aligner 设计
- 标准化 classes：清理噪声标签，按 id/name/label 去重
- 合并 datatype_properties：按 domain + name 组合去重
- 规范 object_properties：按 domain + predicate + range 去重
- relations 按 subject/source + predicate/type + object/target 去重
- 跨文件场景支持 alignment_mappings 与 source_mappings 记录
- 重点：解决问题：重复概念、重复属性、命名不一致、关系重复

## 第12页：OWL Generator 设计
- 将 ontology JSON 转换为 RDF/XML 格式 OWL 文件
- 生成 owl:Class，并支持 rdfs:subClassOf 层级关系
- 生成 owl:DatatypeProperty，自动映射 XSD 数据类型
- 生成 owl:ObjectProperty，兼容 relations 转对象属性
- 写入 edu:sourceFile、edu:sourcePage、edu:sourceRow 等溯源注释
- 重点：导出文件：backend/data/exports/{user_id}/ontology_{timestamp}.owl

## 第13页：前后端接口设计
- POST /upload、POST /upload/batch、POST /generate、POST /generate/start、GET /generate/progress/{job_id}、POST /generate/batch、GET /export、GET /health、/auth/*、/logs/*、/admin/*、/sources/search。

## 第14页：前端页面设计
- Auth、Dashboard、Upload、Result、DataSourceSearch、AuditCenter、GenerationRecords、LogManagement、UserManagement、AdminLogManagement 等页面。

## 第15页：数据溯源设计
- build_trace_map 将本体元素反查 clean_data.records
- 记录来源文件、页面、表格编号、行索引和字段内容
- /sources/search 支持按类、属性、关系、来源文件检索
- OWL 中写入 sourceFile、sourcePage、sourceRow 等注释
- 已实现基础溯源；表格行级定位依赖 PDF 表格抽取质量，仍需继续完善
- 重点：答辩表述：已实现文件级/页面级/表格级基础溯源，精确行级溯源待增强

## 第16页：日志与用户管理
- 用户注册登录与 Bearer Token 鉴权，管理员角色可查看用户信息
- 系统运行日志写入 backend/data/logs/system.log
- SQLite 记录 operation_logs、generation_records、question_records
- 上传、生成、导出、批量生成等关键操作均写入审计记录
- 前端提供个人记录页、审计中心和管理员日志页面
- 重点：支撑能力：可追踪、可审计、便于演示与问题排查

## 第17页：关键问题与解决方案
- 用表格说明端口、文件路径、LLM 配置、本体准确率、OWL 完整性、表格抽取等问题及解决方案。

## 第18页：项目创新点
- 大模型驱动教育本体构建，提升语义识别能力
- PDF 非结构化/半结构化数据自动转结构化本体
- Schema 匹配 + 本体对齐结合，多层次标准化
- 支持 OWL 标准导出并保留来源信息
- Vue + FastAPI 前后端一体化可视化操作
- 增加日志审计与数据溯源，提升系统可信度

## 第19页：系统运行效果
- 当前未发现真实界面截图文件，PPT 使用代码分析生成的运行效果示意图，明确标注“示意图”。

## 第20页：总结与展望
- 总结 PDF 到 OWL 自动化流程、前后端联动和 LLM 辅助本体构建；展望关系识别、多文件融合、行级溯源、知识图谱可视化和人工审核闭环。

