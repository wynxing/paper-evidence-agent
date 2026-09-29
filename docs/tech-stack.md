# 技术选型：论文引文证据核验 Agent

状态：设计稿\
版本：0.6\
日期：2026-09-28\
作者：Wynn\
读者：实现\
相关文档：[术语表](glossary.md)、[产品需求](prd.md)、[架构设计](architecture.md)、[测试方案](test-plan.md)

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
- 决定：用 SQLite 保存本地任务、证据、paper agent 的判断、诊断记录和作者反馈。只对当前被引文献的段落建 FTS5 全文索引，使用 `unicode61` 分词，并以 BM25 排序。[FTS5](https://www.sqlite.org/fts5.html)
- 不选的方案：首版不使用向量数据库。
- 后果：这是限定文献范围的检索。保留词汇基线，但加入文献语言查询生成、一次补充检索及段落邻居读取。先用首版语义验收集定位跨语言、同义改写和上下文遗漏；嵌入检索是可评估的候选，不是原则性禁用。见 [待决](#待决)。

**规则**：首版接受中文或英文论断，只自动处理可确认的英文 PMC 正文，查询生成输出英文普通检索词。以 JATS 正文版本的语言声明和解析出的实际内容核对语言；元数据仅声明英文但正文不符、语言不明或所需内容为未支持语言时，返回 `SOURCE_LANGUAGE_UNSUPPORTED`，不凭英文摘要替代正文。中文分词、全文翻译和额外 tokenizer 扩展不在首版。

**规则**：queries 中每项为普通词组，不是 MATCH 程序。程序按 Unicode 空白拆词、对每个词内部双引号加倍后用双引号包裹，再以程序固定的 OR 合并去重词项，最后作为 SQL 参数绑定；AND/OR/NOT/NEAR、括号、星号和冒号都不作为用户操作符解释。不把整段长查询直接短语化。只含标点或空白、无可索引字符的查询属于 MODEL_INVALID_OUTPUT，可使用已有一次修复；合法构造后数据库/索引异常为 RETRIEVAL_FAILED，不转为零命中，也不让模型修 SQL。[FTS5 查询语法](https://www.sqlite.org/fts5.html#full_text_query_syntax)

## D5 流程编排

- 状态：已采纳
- 背景：身份解析、许可检查、获取、检索、判断和证据校验需要明确的出口。仓库不实现第二名 agent。
- 决定：用 LangGraph 把身份、许可、获取、检索、判断和证据校验写成有界节点。图谱只有一个 paper agent，允许在明确预算内多步调用模型；调用顺序与终止条件见 [执行流程](architecture.md#2-执行流程与状态)。工具只执行当前来源内的只读查询。[LangGraph 概述](https://docs.langchain.com/oss/python/langgraph/overview)
- 不选的方案：不在图谱里编排内部评审。不允许自治 agent 任意联网或改写任务目标。
- 后果：节点出口必须落到 [任务状态](glossary.md#2-任务状态) 中的一种。

## D6 模型适配

- 状态：已采纳，替代原 SDK 直连方案。
- 背景：统一模型接入、密钥与故障恢复，同时把产品可用性策略和固定配置评测分开。
- 决定：`LangGraph → OpenAI 兼容客户端 → 本机 LiteLLM Proxy → 上游模型`。业务代码只使用模型别名 `paper-default`，默认映射 Agnes 的 `agnes-2.5-flash` Chat Completions。上游地址、密钥和映射由 Proxy 配置管理，不在应用中重复实现供应商适配。[Proxy 接入](https://docs.litellm.ai/docs/proxy/quick_start)、[Agnes 接口](https://agnes-ai.com/zh-Hans/docs/agnes-25-flash)
- 部署：独立本地进程及配置文件，绑定回环地址并配置访问凭据；也可显式连接已有兼容网关。版本在实现时锁定。不引入 Redis、PostgreSQL、管理后台或团队计费系统。共享网关若不能保证授权路由、预算和逐次尝试记录，不宣称符合本规范。
- 不假定上游支持特定 JSON Schema 响应参数。使用受校验的结构化动作；仅在验证兼容性后启用供应商结构化输出能力。

| 配置 | 日常核验 `daily` | 评测 `evaluation` |
| --- | --- | --- |
| 模型 | 默认别名；备用模型须先配置并取得接收方授权 | 别名固定到单个部署；禁止自动跨模型或部署切换 |
| 恢复 | 短暂故障可恢复；备用调用占用同一恢复槽位 | 只允许同一部署的短暂故障重试 |
| 缓存 | 首版关闭模型响应缓存 | 禁用模型响应缓存，固定来源快照 |
| 固定记录 | 授权与运行配置快照 | 另冻结提示词、检索配置、模型部署、来源及数据集、预算 |

Proxy 支持按请求禁用回退；评测同时限制别名映射，不能仅凭别名声称模型固定。[回退说明](https://docs.litellm.ai/docs/proxy/reliability)

**规则**：客户端自动重试关闭。网络恢复只归 Proxy；结构或摘录输出修复归工作流。每个逻辑请求最多两个上游尝试（首次加一次恢复）；日常模式若配置了已授权备用部署则恢复到该部署，否则重试原部署；评测仅重试原部署。不能先重试再叠加回退，备用尝试也不能再重试。连接失败、超时、429 和暂时性 5xx 才可恢复；遵守 Retry-After。认证、参数错误不盲目重试；不因「证据不足」、判断方向或内容拒绝而换模型。禁止其他隐式回退和重复 SDK 重试。流程预算见 [执行流程](architecture.md#2-执行流程与状态)。

**规则**：Proxy 和应用日志、轨迹不记录论断正文、提示词、响应文本或密钥。关闭消息回调日志及详细调试，只投影允许的元数据；错误响应同样脱敏。`turn_off_message_logging` 不等于全链路已无泄漏，仍需检查实际 stdout、文件与回调载荷。[日志配置](https://docs.litellm.ai/docs/proxy/config_settings)

- 后果：逐次关联逻辑请求和上游尝试；最终响应不足以证明中间尝试，需本地元数据回调/轨迹。模型版本不能验证时记为未知，usage 缺失记为 `null`。输出结构见 [诊断包](glossary.md#6-诊断包)。paper agent 的标签不是真值，不新增内部评审 Agent。

## D7 可观测性

- 状态：已采纳
- 背景：测试方案需要按阶段核对工具调用、耗时和错误码。
- 决定：使用 OpenTelemetry Python SDK 记录本地轨迹，提供默认关闭的 Langfuse 导出。[手动埋点](https://opentelemetry.io/docs/languages/python/instrumentation/)
- 不选的方案：不把轨迹当作模型内部推理记录。
- 后果：span 的字段边界见 [架构设计](architecture.md#4-本地记录与失败处理)。诊断包的执行与模型元数据分别投影到术语表的 `execution` 和 `model_calls`，不导出原始响应。

**规则**：提供可选 Langfuse OTLP/HTTP 导出，默认关闭；仅在配置端点、凭据和观测接收方授权后启用。先脱敏再导出；本地记录是诊断依据，异步有界导出失败只记录本地观测警告，不重试业务请求、不改变任务结果，不阻塞 worker 释放。观测接收方独立于模型接收方，配置摘要包含启用状态和接收方，密钥不进入摘要或日志。[Langfuse OTLP](https://langfuse.com/integrations/native/opentelemetry)

- 不强制本机部署 Langfuse 服务栈；可连接用户已提供的实例。接入已有服务不等于没有部署成本，自托管需额外存储组件。[部署架构](https://langfuse.com/self-hosting)
- Langfuse 用于分析调用链、延迟、成本和错误；外部测试 Agent 从授权轨迹与诊断包取数、分析并输出报告，流程见 [外部评审](test-plan.md#1-外部评审怎么做)。接入仪表盘不等于完成自动归因，须用隐藏注入真因验证。

## D8 验证

- 状态：已采纳
- 背景：规则、接口和作者复核流程需要分开检查。研究指标不能用界面演示代替。
- 决定：pytest 与 Playwright 按 [测试方案](test-plan.md) 执行。首版包含人工核对真实来源的小规模语义验收；大规模研究评测不作为参赛验收的前置条件。
- 不选的方案：不用一次性的手工演示代替上述检查，也不用研究数据集代替测试方案里的用例。
- 后果：依赖版本在实际开发时锁定。仓库目前没有应用代码、模型密钥、论文语料或性能结果。

## D9 文献来源

- 状态：已采纳
- 背景：首版必须先确认文献身份、可处理的全文及其版本，再在该文献内找证据。用户指定的是某一篇 DOI，不是一篇“相似”文献。
- 决定：
  1. 用 [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) 核对 DOI、题名、作者和发表信息。界面仍要求作者确认解析出的题名。
     Crossref `/works/{doi}` 404 时先查 `/works/{doi}/agency`；确认非 Crossref 则 REGISTRATION_AGENCY_UNSUPPORTED，确认 Crossref 则 METADATA_NOT_FOUND。机构也未找到时，用 DOI 官方解析服务做不跟随跳转的解析检查：有效跳转仅证明可解析，返回 METADATA_NOT_FOUND；明确未找到才 DOI_UNRESOLVABLE。认证、429、5xx、超时等按上游故障处理，不能证明 DOI 不存在；异常协议响应按 UPSTREAM_INVALID_REQUEST 处理。所有请求仅去固定官方入口，不跟随到任意出版商页面。
  2. 用 [PMC ID Converter](https://pmc.ncbi.nlm.nih.gov/tools/id-converter-api/) 把 DOI 映射到 PMCID。
  3. 用 [OpenAlex](https://help.openalex.org/data/works/open-access/) 辅助发现开放位置、版本和许可线索。OpenAlex 的“可免费阅读”不等于允许获取并发送全文。
  4. 通过 [PMC OAI-PMH](https://pmc.ncbi.nlm.nih.gov/tools/oai/) 获取允许复用的 JATS 全文，并逐篇检查该版本的许可声明。
  5. **规则**：首版自动处理的全文，必须已经取得结构化正文，且该版本的许可明确为 CC0 或 CC BY。
- 不选的方案：不抓取受限 PDF。不把论文全文提交到 Git。不用 OpenAlex 的开放获取字段单独充当许可凭据。
- 后果：许可缺失或冲突用 `LICENSE_UNKNOWN`，已知但不在首版支持范围的许可用 `LICENSE_UNSUPPORTED`，无可用 PMC 来源用 `SOURCE_UNAVAILABLE`，已获取内容缺失或无法可靠解析用 `CONTENT_INCOMPLETE`。这些情况均为 `BLOCKED`、兼容标签「无法核验来源」，实际主文案按术语表区分具体来源或处理/内容原因；外部请求失败不冒充来源不存在。保存 PMCID、DOI、获取入口、许可、版本、获取时间和内容哈希。只索引获准处理的段落。

上游密钥仅配置在 Proxy 的本机环境变量中，应用只持有网关访问凭据。启动任务前，界面展示整次核验的数据范围、接收方、逻辑请求及上游尝试预算；备用接收方未被授权时不得调用。确认绑定运行配置快照，配置改变不得扩大已有授权。未经确认只做 DOI 的只读元数据查询。若把诊断包交给仓库外的评审 agent，另行展示将发送的字段并取得同意。默认包遮盖未发表论断。Claude、Cursor 是这类评审的例子，不是字段契约，也不进入应用依赖。

## D10 暂不采用

- 状态：已采纳
- 背景：下面的方案会扩大核验对象或首版基础设施范围；不代表这些技术原则上不可用。
- 决定：首版不采用下列方案。
  - 全网自由搜索和自动引用补全。首版只核对指定 DOI。
  - 用摘要代替全文来声称全文没有相关证据。摘要级结果只作研究基线，见 [研究评测](evaluation.md)。
  - 向量数据库、自由协商的多 Agent，以及网关管理后台、团队计费、Redis、PostgreSQL。
  - 把整篇 PDF 解析当作首版能力。以后可评估 [GROBID](https://grobid.readthedocs.io/en/latest/Grobid-service/) 识别引文标记和参考文献，并让作者确认含糊对应。解析准确率和页码定位未单独评测前，解析结果不充当确定的引用关系。
- 不选的方案：不把以上任何一项写入首版验收。
- 后果：整篇论文模式若要做，先拆成现有的单条任务。见 [架构设计](architecture.md#5-后续扩展接口)。

## D11 不改用赛题推荐栈

- 状态：已采纳
- 背景：[赛题](https://www.boxuegu.com/matchTrack/detail/?id=10041)建议 Dify、Coze、LangChain、LlamaIndex、DeepSeek、Qwen、GLM、DeepEval、RAGAS、JMeter 和 Locust。这些是建议，不是必选依赖。
- 决定：首版保持已经采纳的 Vue、FastAPI、LangGraph、OpenAI 兼容客户端、LiteLLM Proxy、默认 Agnes、SQLite FTS5、pytest、Playwright 和本地 OpenTelemetry（可选 Langfuse 导出）。Dify、Coze、DeepEval、RAGAS 和 JMeter 不进入依赖。Claude 与 Cursor 的 SDK 也不进入依赖；它们只在仓库外担任评审。性能测量遵守测试方案，不引入 Locust 或分布式压测。
- 不选的方案：不为了贴近推荐名单而更换编排框架或检索方案。
- 后果：参赛说明要写明这是有意选择。目录和模块边界以 [架构设计](architecture.md#代码布局) 为准。

## 待决

- 嵌入检索：根据首版真实来源测试的 Recall@k、跨语言及改写遗漏，决定是否另行引入；与查询改写后的 FTS5 做消融对照，本次不增加该依赖。
- GROBID 的引文映射准确率和页码定位。未评测前保持 [D10](#d10-暂不采用)。
