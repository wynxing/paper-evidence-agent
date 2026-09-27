# 技术选型：论文引文证据核验 Agent

状态：设计稿  
版本：0.1  
日期：2026-09-27  
作者：Wynn  
读者：实现  
相关文档：[术语表](glossary.md)、[产品需求](prd.md)、[架构设计](architecture.md)、[研究评测](evaluation.md)

句子标记见 [术语表](glossary.md)。本文只记录已经采纳的技术决定、不采纳的方案和尚未选择的点。产品定位见 [产品需求](prd.md)。用户可见的验收不在这里重复。

每条决定包含状态、背景、决定、不选的方案和后果。状态为“已采纳”时，表示设计稿里的规则，不表示组件已经接入或性能已经测过。

## D1 前端

- 状态：已采纳
- 背景：作者需要把论断和原文片段放在一起复核。
- 决定：使用 Vue 3、TypeScript 和 Vite。
- 不选的方案：本文不比较其他前端框架。更换框架前另开决定。
- 后果：前端不保存模型密钥。

## D2 接口

- 状态：已采纳
- 背景：文献处理、模型调用和研究脚本需要共用一套类型和校验。
- 决定：使用 Python 3.12、FastAPI 和 Pydantic。API 只监听本机。
- 不选的方案：不把校验逻辑拆到另一种语言。
- 后果：接口字段和错误行为见 [架构设计](architecture.md#3-接口)。模型输出的结构校验也用 Pydantic。

## D3 任务执行

- 状态：已采纳
- 背景：外部请求和模型调用会拖慢页面，首版只有一台机器上的一个用户流程。
- 决定：使用单独的 Python 单进程执行器，从 SQLite 领取任务。
- 不选的方案：不引入 Redis 或分布式队列。
- 后果：执行器一次处理一个任务。并发上限就是这个单进程。

## D4 状态与检索

- 状态：已采纳
- 背景：核验范围是当前这一篇被引文献，不是全库语义搜索。
- 决定：用 SQLite 保存本地任务、证据、Agent 评审、诊断记录和作者反馈。只对当前被引文献的段落建 FTS5 全文索引，并以 BM25 排序。[FTS5](https://www.sqlite.org/fts5.html)
- 不选的方案：首版不使用向量数据库。
- 后果：这是限定文献范围的检索。词汇不匹配会损失召回。是否加嵌入检索见 [待决](#待决)，并由 [研究评测](evaluation.md) 的检索率决定。

## D5 流程编排

- 状态：已采纳
- 背景：身份解析、许可检查、获取、检索、初判、独立评审和证据校验需要明确的出口，不能变成自由协商的多 Agent。
- 决定：用 LangGraph 把这些步骤写成有界节点。测试 Agent 离线读取诊断包。工具只执行只读查询。[LangGraph 概述](https://docs.langchain.com/oss/python/langgraph/overview)
- 不选的方案：不允许自治 Agent 任意联网或改写任务目标。
- 后果：节点出口必须落到 [任务状态](glossary.md#2-任务状态) 中的一种。

## D6 模型适配

- 状态：已采纳
- 背景：需要一个稳定的上游接口，同时保留以后换模型做对照的可能。
- 决定：使用 LiteLLM Python SDK。默认调用 Agnes 的 `agnes-2.5-flash` Chat Completions。禁用 LiteLLM 自动模型回退。无效输出允许一次受控重试，仍然无效则记录 `MODEL_INVALID_OUTPUT`。[LiteLLM](https://docs.litellm.ai/docs/)、[Agnes 2.5 Flash](https://agnes-ai.com/zh-Hans/docs/agnes-25-flash)
- 不选的方案：不使用 LiteLLM Proxy。DeepSeek 只作为后续对照候选，不在同一次主要实验中自动切换。不假定 Agnes 支持某种特定的 JSON Schema 响应参数。
- 后果：初判和评审在隔离上下文中各调用一次。即使提示词不同，同一模型仍可能出现相关错误。实验分别记录每次调用的模型标识、参数、提示词版本、调用次数和 token 用量。一致意见不是真值。

## D7 可观测性

- 状态：已采纳
- 背景：测试 Agent 需要按阶段查看工具调用、耗时和错误码。
- 决定：使用 OpenTelemetry Python SDK 记录本地轨迹。[手动埋点](https://opentelemetry.io/docs/languages/python/instrumentation/)
- 不选的方案：不把轨迹当作模型内部推理记录。
- 后果：span 的字段边界见 [架构设计](architecture.md#4-本地记录与失败处理)。诊断包只投影术语表中的 `execution` 字段。

## D8 验证

- 状态：已采纳
- 背景：规则、接口和作者复核流程需要分开检查。研究指标不能用界面演示代替。
- 决定：pytest 检查规则和接口。Playwright 检查作者复核流程。实验评测使用冻结数据集，协议见 [研究评测](evaluation.md)。
- 不选的方案：不用一次性的手工演示代替上述检查。
- 后果：依赖版本在实际开发时锁定。仓库目前没有应用代码、模型密钥、论文语料或性能结果。

## D9 文献来源

- 状态：已采纳
- 背景：首版必须先确认文献身份、可处理的全文及其版本，再在该文献内找证据。用户指定的是某一篇 DOI，不是一篇“相似”文献。
- 决定：
  1. 用 [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) 核对 DOI、题名、作者和发表信息。界面仍要求作者确认解析出的题名。
  2. 用 [PMC ID Converter](https://pmc.ncbi.nlm.nih.gov/tools/id-converter-api/) 把 DOI 映射到 PMCID。
  3. 用 [OpenAlex](https://help.openalex.org/data/works/open-access/) 辅助发现开放位置、版本和许可线索。OpenAlex 的“可免费阅读”不等于允许获取并发送全文。
  4. 通过 [PMC OAI-PMH](https://pmc.ncbi.nlm.nih.gov/tools/oai/) 获取允许复用的 JATS 全文，并逐篇检查该版本的许可声明。
  5. **规则**：首版自动处理的全文，必须已经取得结构化正文，且该版本的许可明确为 CC0 或 CC BY。
- 不选的方案：不抓取受限 PDF。不把论文全文提交到 Git。不用 OpenAlex 的开放获取字段单独充当许可凭据。
- 后果：许可缺失、版本间许可冲突或未取得全文时，任务为 `BLOCKED`，错误码 `LICENSE_UNKNOWN` 或 `CONTENT_INCOMPLETE`，结果标签为「无法核验来源」。保存 PMCID、DOI、获取入口、许可、版本、获取时间和内容哈希。只索引获准处理的段落。

密钥放在本机环境变量中。启动云模型调用前，界面告知将向 Agnes 发送论断文本和候选开放片段，并取得本次核验的确认。未经确认只做 DOI 的只读元数据查询。诊断包交给外部测试 Agent 时，另行展示将发送的字段并取得同意。默认包遮盖未发表论断。这里的外部测试 Agent 是角色；Codex 只是一种可能的调用方，不是字段契约的一部分。

## D10 暂不采用

- 状态：已采纳
- 背景：下面的方案会扩大核验对象，或让首版无法证明判断针对的是用户指定的文献。
- 决定：首版不采用下列方案。
  - 全网自由搜索和自动引用补全。首版只核对指定 DOI。
  - 用摘要代替全文来声称全文没有相关证据。摘要级结果只作研究基线，见 [研究评测](evaluation.md)。
  - 向量数据库、自由协商的多 Agent、LiteLLM Proxy。
  - 把整篇 PDF 解析当作首版能力。以后可评估 [GROBID](https://grobid.readthedocs.io/en/latest/Grobid-service/) 识别引文标记和参考文献，并让作者确认含糊对应。解析准确率和页码定位未单独评测前，解析结果不充当确定的引用关系。
- 不选的方案：不把以上任何一项写入首版验收。
- 后果：整篇论文模式若要做，先拆成现有的单条任务。见 [架构设计](architecture.md#5-后续扩展接口)。

## 待决

- 嵌入检索：只有 FTS5 的检索率实验表明需要时才加入，并做消融对照。
- 上游限流是否从 `UPSTREAM_TIMEOUT` 拆出独立错误码。拆开之前，超时和限流共用该码。
- GROBID 的引文映射准确率和页码定位。未评测前保持 [D10](#d10-暂不采用)。
