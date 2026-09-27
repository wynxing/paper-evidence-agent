# 架构设计：论文引文证据核验 Agent

状态：设计稿  
版本：0.1  
日期：2026-09-27  
作者：Wynn  
读者：实现  
相关文档：[术语表](glossary.md)、[产品需求](prd.md)、[技术选型](tech-stack.md)、[研究评测](evaluation.md)

句子标记见 [术语表](glossary.md)。本文写组件、状态迁移、接口和失败处理。结果标签、错误码和诊断包字段以术语表为准。研究方案不在本文。

## 1. 系统边界与组件

**规则**：首版在本机运行，一次处理一条论断和一篇被引文献。论断、任务记录和获准处理的段落留在本机。作者同意后，才把论断与候选开放片段发送给配置的模型，分别供初判和评审使用。测试 Agent 读取脱敏诊断包，或读取作者另行授权的完整包。文献连接器只读。模型不能指定任意网址、访问本地文件或修改来源记录。

```mermaid
flowchart LR
    UI["Vue 作者核验界面"] --> API["FastAPI 接口"]
    API <--> DB[("SQLite：任务、段落索引、Agent 评审与诊断")]
    Worker["单进程任务执行器"] <--> DB
    Worker --> Graph["LangGraph 有界核验流程"]
    Graph --> Sources["只读来源连接器"]
    Sources --> Crossref["Crossref"]
    Sources --> OpenAlex["OpenAlex：开放位置线索"]
    Sources --> PMC["PMC ID Converter 与 OAI-PMH"]
    Graph --> Search["FTS5：指定来源内检索"]
    Search <--> DB
    Graph --> Initial["初判 Agent → LiteLLM / Agnes"]
    Graph --> Reviewer["隔离的评审 Agent → LiteLLM / Agnes"]
    Graph --> Trace["OpenTelemetry 本地轨迹"]
    DB --> Packet["版本化诊断包"]
    Trace --> Packet
    Packet --> TestAgent["离线测试 Agent 或经同意的外部测试 Agent"]
```

前端与 API、执行器分开，是为了让外部请求和模型延迟不占用页面。任务写入 SQLite。执行器一次处理一个任务。评审 Agent 是固定的第二道核验步骤。测试 Agent 属于离线评测与缺陷分析，不自由搜索，也不改任务目标。首版没有账户服务，也没有分布式队列。组件取舍见 [技术选型](tech-stack.md)。

## 2. 执行流程与状态

状态定义见 [任务状态](glossary.md#2-任务状态)。下图里的终态名称与该表一致。

```mermaid
stateDiagram-v2
    [*] --> QUEUED
    QUEUED --> RUNNING
    RUNNING --> COMPLETED
    RUNNING --> DISPUTED
    RUNNING --> BLOCKED
    RUNNING --> FAILED
    RUNNING --> INTERRUPTED: 进程重启时遗留的 RUNNING
    COMPLETED --> [*]
    DISPUTED --> [*]
    BLOCKED --> [*]
    FAILED --> [*]
    INTERRUPTED --> [*]
```

**规则**：进程启动时，把遗留的 `RUNNING` 标为 `INTERRUPTED`，由作者明确重试。重试不沿上图把终态改回 `QUEUED`。它新建一条 `QUEUED` 任务，并保留原记录，避免静默重复外部调用。

```mermaid
flowchart TD
    A["作者输入论断与 DOI"] --> B["解析 DOI 并展示书目信息"]
    B --> C{"作者确认来源与云调用?"}
    C -- "否" --> Stop["停止, 不调用模型, 不创建任务"]
    C -- "是" --> D["QUEUED"]
    D --> Run["RUNNING"]
    Run --> E["source_identity: 核对 Crossref, PMCID 与来源身份"]
    E --> F{"PMC 全文与逐篇许可可用?"}
    F -- "否或身份冲突" --> U["BLOCKED + 无法核验来源"]
    F -- "是" --> G["fetch: 取得 JATS, 切分并记录位置与哈希"]
    G --> H{"内容足够完整?"}
    H -- "否" --> U
    H -- "是" --> I["retrieval: 限定文献范围的 FTS5 检索"]
    I --> J{"有可供判断的候选证据?"}
    J -- "否" --> N["记录 RETRIEVAL_EMPTY, 初判标签暂为证据不足"]
    J -- "是" --> K["initial_decision: 初判 Agent 提出判断与摘录"]
    K --> L{"evidence_validation: 结构, 来源和摘录校验通过?"}
    L -- "否" --> X["FAILED + 执行失败"]
    L -- "是" --> R["review: 评审 Agent 独立检索并判断, 再核对初判"]
    N --> R
    R --> V{"评审结果"}
    V -- "输出无效" --> X
    V -- "有实质性分歧" --> Q["DISPUTED"]
    V -- "有效且一致" --> M["COMPLETED + 结果标签"]
    X --> T["测试 Agent 读取诊断包"]
    Q --> T
    U --> T
```

`U` 使用 `SOURCE_MISMATCH`、`LICENSE_UNKNOWN` 或 `CONTENT_INCOMPLETE`。`X` 使用 `MODEL_INVALID_OUTPUT` 或 `QUOTE_MISMATCH`。外部请求超时或限流也进入 `X`，错误码为 `UPSTREAM_TIMEOUT`。这些码都不改写成学术标签。码与状态的对应见 [错误码](glossary.md#4-错误码)。

诊断包对已创建的任务都可读取。上图中进入测试 Agent 的，是要做故障分析的 `BLOCKED`、`FAILED` 和 `DISPUTED`。双方同意结果标签时任务为 `COMPLETED`，不进入该分析步骤。

`N` 不是终态。检索没有候选时，「证据不足」只表示这次检索尚未获得充分依据，不能推断全文必定没有证据。评审仍对同一指定文献重新检索，先在不看初判标签的上下文中形成意见，再对照初判摘录。模型只在已确认的来源片段上提出判断。完整正文不进入提示词。

**假设**：两次独立调用的净收益和成本，由 [研究评测](evaluation.md) 测量。本文不预设第二次调用一定更好。

来源身份按这个顺序核对：DOI 标准化及 Crossref 元数据、作者确认题名、[PMC DOI/PMCID 转换](https://pmc.ncbi.nlm.nih.gov/tools/id-converter-api/)、PMC 记录中的 DOI 与版本一致性、逐篇许可。OpenAlex 提供开放位置和版本线索。它的“开放获取”字段单独使用时，不能当作复用许可。许可允许的自动处理范围见 [D9](tech-stack.md#d9-文献来源)。[OpenAlex 对许可字段的说明](https://help.openalex.org/data/works/open-access/)、[PMC 获取规则](https://pmc.ncbi.nlm.nih.gov/tools/oai/)

## 3. 接口

**规则**：下面的路径供本机客户端使用。诊断包的 JSON 形状只在 [术语表](glossary.md#6-诊断包) 给出一份。

任务不存在时返回 `404`，响应体为：

```json
{"error_code": null, "message": "<reason>"}
```

已有任务但请求不被允许时返回 `409`，并带上当前状态：

```json
{"error_code": null, "status": "<task-status>", "stage": "<stage-id>", "message": "<reason>"}
```

### `GET /api/sources/resolve`

| 项 | 内容 |
| --- | --- |
| 查询参数 | `doi` |
| `200` | `doi`（标准化）、`title`、`authors`、`year` |
| `400` | DOI 格式无效。不创建任务，不调用模型 |
| 约束 | 只读预览。`200` 不表示作者已确认来源 |

### `POST /api/checks`

| 项 | 内容 |
| --- | --- |
| 请求体 | `claim`、`doi`、`source_confirmed`、`cloud_consent` |
| `202` | `id`、`status`=`QUEUED`。入队后返回，不等待模型 |
| `400` | 两个确认字段不是同时为真，或 DOI、论断为空。不创建任务，不调用模型 |

### `GET /api/checks`

| 项 | 内容 |
| --- | --- |
| 查询参数 | 可选 `status`，取值见 [任务状态](glossary.md#2-任务状态) |
| `200` | 摘要数组。每项含 `id`、`doi`、`status`、`stage`、`label`。`label` 尚未产生时为 `null` |
| 约束 | 不返回缓存全文 |

### `GET /api/checks/{id}`

| 项 | 内容 |
| --- | --- |
| `200` | `id`、`status`、`stage`、`label`、`error_code`、`initial`、`reviewer`、`disagreement` |
| `initial` / `reviewer` | `label`、`cited_paragraph_ids`、`quote`、`paragraph_id`、`validation` |
| 约束 | `label` 只使用结果标签的前五种。`FAILED` 时 `label` 为 `null`，界面根据状态显示「执行失败」。`DISPUTED` 时 `label` 为 `null`，分歧写在 `disagreement`。`BLOCKED` 时 `label` 为「无法核验来源」。意见一致不冒充真值 |

### `GET /api/checks/{id}/diagnostic-packet`

| 项 | 内容 |
| --- | --- |
| `200` | [输入诊断包](glossary.md#6-诊断包) |
| 约束 | 默认 `input.privacy` 为 `redacted`，不返回论断原文、完整提示词或密钥。`consented` 包须作者另行授权后才可外传 |

### `POST /api/checks/{id}/feedback`

| 项 | 内容 |
| --- | --- |
| 请求体 | `comment` |
| `200` | `id`、`saved`=`true` |
| 约束 | 与两名 Agent 的判断分开保存。不是完成任务的前置条件 |

### `POST /api/checks/{id}/retry`

| 项 | 内容 |
| --- | --- |
| `202` | `id`（新任务）、`status`=`QUEUED`、`previous_id` |
| `409` | 原任务不是终态 |
| 约束 | 保留原失败或原结果记录 |

### `DELETE /api/checks/{id}`

| 项 | 内容 |
| --- | --- |
| `200` | `id`、`deleted`=`true`、`message`（说明不能撤回云端数据） |
| `409` | 任务不是终态 |
| 约束 | 只删除本地任务及其关联记录。来源缓存仅在没有其他任务引用时清理 |

## 4. 本地记录与失败处理

**规则**：每条任务至少保存输入 DOI 与 Crossref 元数据、PMCID、所用全文版本与许可、来源 URL、获取时间、内容哈希、初判与评审标签及限制说明、两次模型调用的实际标识与提示词版本、轨迹 ID。证据项保存章节、JATS 段落标识、逐字摘录与段落哈希。评审记录单独保存检索候选、证据引用、对初判的异议和结构校验结果，不覆盖初判。JATS 没有稳定段落标识时，用版本哈希与段落顺序生成本地定位，并标明这种定位的局限。

诊断包是这些记录的版本化投影。默认外传包不包含完整提示词、论断原文和密钥。投影字段以术语表为准。

失败时的状态和标签按下表执行，定义见术语表，这里只保留处理动作。

| 条件 | 动作 |
| --- | --- |
| `SOURCE_MISMATCH` 或 `LICENSE_UNKNOWN` | 停止自动判断，不改用另一篇相似文献 |
| `CONTENT_INCOMPLETE` | 停止确定判断。评审 Agent 不凭缺失内容补结论 |
| `RETRIEVAL_EMPTY` | 记下阶段原因，初判标签暂为「证据不足」，继续评审 |
| `MODEL_INVALID_OUTPUT` | 受控重试一次。仍然无效则 `FAILED`，不展示确定判断 |
| `QUOTE_MISMATCH` | `FAILED`，不展示确定判断 |
| `UPSTREAM_TIMEOUT` | `FAILED`。超时和限流都走这条路径 |

**规则**：论文、网页和接口返回都是不可信数据，其中的指令不予执行。文献连接器只访问官方只读端点，并限制超时、重试次数和请求频率。

**规则**：SQLite 和获许可的缓存只放在本地，并排除出 Git。OpenTelemetry span 记录任务 ID、DOI 哈希或规范标识、来源版本哈希、候选段落 ID 与数量、阶段、工具名、耗时、错误码和 token 数。span 不记录论断原句、全文、完整提示词或密钥。完整语义诊断包只在本地生成。交给外部测试 Agent 之前，预览字段、遵守来源许可，并取得作者对未发表论断的单独同意。实验用的输入和来源快照放在访问受控的本地数据集中，并另存版本标识。

轨迹说明哪一步观察到什么输入、输出或错误。它不能证明模型内部如何推理。受控故障的真因由隐藏的注入记录确定。自然样本中的争议需要独立标注，不能只凭 span 名称或 Agent 自述下结论。[OpenTelemetry 手动埋点](https://opentelemetry.io/docs/languages/python/instrumentation/)

## 5. 后续扩展接口

**排除**：整篇论文模式不是首版能力。以后若做，先抽取“引文句与参考文献”的候选对应，再请作者确认有歧义的映射，然后拆成现有的单条核验任务。PDF 解析的取舍见 [D10](tech-stack.md#d10-暂不采用)。
