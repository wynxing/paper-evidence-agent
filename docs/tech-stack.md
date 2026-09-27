# 技术选型：论文引文证据核验 Agent

> 状态：设计稿。本文记录拟采用的方案和选择理由，不代表组件已接入或性能已验证。

## 1. 选择原则

核验单位是一条论断与一篇被引文献。首版必须先确认**文献身份、可处理的全文及其版本**，再在该文献内寻找证据。检索结果只是候选；模型判断须接受来源、原文片段和结构校验。产品只评价这条引用关系，不判定论断在整个学科中的最终真伪。

已有产品提供“输入论断和来源、返回判断及证据片段”的功能，例如 [In-Cite Claim Check](https://www.in-cite.com/)。本项目拟研究证据不足时的拒判，以及面向评审 Agent 和测试 Agent 的可复查输出能否改善错误发现与定位；收益须按 [架构与评测设计](architecture.md#6-研究评测设计)验证。

## 2. 应用与数据

| 层次 | 拟采用技术 | 选择理由与边界 |
| --- | --- | --- |
| 前端 | Vue 3、TypeScript、Vite | 构建论断与原文并列的复核界面；前端不保存模型密钥。 |
| API | Python 3.12、FastAPI、Pydantic | 文献处理、模型调用和研究脚本共用 Python 类型与校验逻辑；API 只监听本机。 |
| 任务执行 | 单独的 Python 单进程执行器 | 从 SQLite 领取任务，限制并发并隔离耗时的外部请求；不引入 Redis 或分布式队列。 |
| 状态与索引 | SQLite、FTS5 | 保存本地任务、证据、Agent 评审与诊断记录及作者反馈；仅对**当前被引文献**的段落建全文索引，以 BM25 排序。[FTS5 文档](https://www.sqlite.org/fts5.html) |
| 流程 | LangGraph | 将身份解析、许可检查、获取、检索、初判、独立评审和证据校验表示为有明确出口的节点；测试 Agent 离线读取诊断包，工具仅执行只读查询。[官方文档](https://docs.langchain.com/oss/python/learn) |
| 模型适配 | LiteLLM Python SDK | 统一上游接口。默认接 Agnes 的 `agnes-2.5-flash` Chat Completions；DeepSeek 只作为后续对照候选，不在同一次实验中自动切换。[LiteLLM](https://docs.litellm.ai/docs/)、[Agnes 2.5 Flash](https://agnes-ai.com/zh-Hans/docs/agnes-25-flash) |
| 可观测性 | OpenTelemetry Python SDK | 为可观察的步骤、工具调用、耗时和错误码建立轨迹；轨迹不是模型内部完整推理记录。[官方文档](https://opentelemetry.io/docs/languages/python/instrumentation/) |
| 验证 | pytest、Playwright | 分别检查规则/接口和作者复核流程；实验评测另用冻结数据集执行。 |

首版是**限定文献范围的 RAG**：先确定 DOI 指向的文献，再用 FTS5 检索其结构化全文段落，并把候选片段交给模型判断。RAG 不要求向量数据库。词汇不匹配造成的召回损失应通过检索率测量；只有实验表明需要时，才加入嵌入检索及消融对照。

模型使用固定配置和应用侧 Pydantic 校验。Agnes 文档确认了兼容的调用入口，但此方案不假定其支持某种特定 JSON Schema 响应参数；无效输出允许一次受控重试，仍无效则记录执行失败。初判 Agent 与评审 Agent 在隔离上下文中运行；评审先独立检索指定文献并形成判断，再对照初判的证据与结论。两者即使用不同提示词，同一模型仍可能出现相关错误，不把一致意见当成真值。真实实验须分别记录每次调用的实际模型标识、参数、提示词版本、调用次数和 token 用量；禁用 LiteLLM 自动模型回退，避免同一实验条件混入不同模型。

## 3. 文献来源与许可门槛

1. 用 [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) 核对 DOI、题名、作者和发表信息。DOI 本身不能证明输入者想引用的就是这篇文献；界面要求作者确认解析出的题名。
2. 用 [PMC ID Converter](https://pmc.ncbi.nlm.nih.gov/tools/id-converter-api/) 将 DOI 映射到 PMCID；[OpenAlex](https://help.openalex.org/data/works/open-access/) 仅辅助发现开放位置、版本和许可线索。OpenAlex 的“可免费阅读”不等同于允许本产品获取并发送全文。
3. 通过 [PMC OAI-PMH 接口](https://pmc.ncbi.nlm.nih.gov/tools/oai/) 获取允许复用的 JATS 全文，并逐篇检查该版本的许可声明。首版自动处理范围限定为可取得结构化全文且许可明确为 CC0 或 CC BY 的版本；许可缺失、不同版本许可冲突或未取得全文时停止自动判定，输出机器可读的阻断原因。
4. 保存 PMCID、DOI、获取入口、许可、版本、获取时间和内容哈希。只索引获准处理的段落；不抓取受限 PDF，也不把论文全文提交到 Git。PMC 对自动获取渠道及逐篇许可均有明确要求。[PMC 说明](https://pmc.ncbi.nlm.nih.gov/tools/oai/)

用户输入的论断可能尚未发表。启动云模型调用前，界面必须告知初判和评审将向 Agnes 发送**论断文本和候选开放片段**，并取得本次核验的明确确认；未经确认不发送论断，只进行 DOI 的只读元数据查询。若将诊断包交给 Codex 等外部测试 Agent，须另行展示将发送的字段并取得明确同意；默认包遮盖未发表论断。密钥仅放在本机环境变量中，轨迹不记录论断原文、完整提示词、全文或密钥。

## 4. 暂不采用的方案

- **全网自由搜索与自动引用补全**：范围难以界定，也难以证明系统判定的是用户指定的来源；首版只核对指定 DOI。
- **摘要代替全文**：摘要级结果可用于研究基线，不能据此声称全文没有相关证据。[SciFact 的证据语料是摘要](https://github.com/allenai/scifact/blob/master/doc/data.md)。
- **向量数据库、自由协商的多 Agent 与 LiteLLM Proxy**：首版按一篇文献检索、单机运行；初判、评审与离线诊断各有固定输入输出，不允许自治 Agent 任意联网或改写任务目标。增加组件前先验证实际收益。
- **整篇 PDF 解析**：后续可评估 [GROBID](https://grobid.readthedocs.io/en/latest/Grobid-service/) 识别引文标记与参考文献，并让作者确认含糊的对应关系；不将其描述为首版能力。

依赖版本在实际开发时锁定并记录。仓库目前尚无应用代码、模型密钥、论文语料或性能结果。
