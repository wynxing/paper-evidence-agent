# 架构设计：论文引文证据核验 Agent

状态：设计稿\
版本：0.4\
日期：2026-09-28\
作者：Wynn\
读者：实现\
相关文档：[术语表](glossary.md)、[产品需求](prd.md)、[测试方案](test-plan.md)、[技术选型](tech-stack.md)

句子标记见 [术语表](glossary.md)。本文写组件、代码布局、状态迁移、接口和失败处理。结果标签、错误码和诊断包字段以术语表为准。参赛测试见 [测试方案](test-plan.md)。研究方案不在本文，也不进入运行时依赖。

## 1. 系统边界与组件

**规则**：首版在本机运行，一次处理一条论断和一篇被引文献。论断、任务记录和获准处理的段落在本机保存。作者同意后，才把论断与候选开放片段发送给配置的模型，供 paper agent 使用。一个 paper agent 在预算内完成多步核验。模型请求统一经过本机 LiteLLM Proxy，整次任务的接收方和预算先获授权。诊断包和轨迹交给仓库外的评审 agent；它们不在本进程内。文献连接器只读。模型不能指定任意网址、访问本地文件或修改来源记录。

```mermaid
flowchart LR
    UI["Vue 作者核验界面"] --> API["FastAPI 接口"]
    API <--> DB[("SQLite：任务、段落索引与诊断")]
    Worker["单进程任务执行器"] <--> DB
    Worker --> Graph["LangGraph 有界核验流程"]
    Graph --> Sources["只读来源连接器"]
    Sources --> Crossref["Crossref"]
    Sources --> OpenAlex["OpenAlex：开放位置线索"]
    Sources --> PMC["PMC ID Converter 与 OAI-PMH"]
    Graph --> Search["FTS5：指定来源内检索"]
    Search <--> DB
    Graph --> Paper["paper agent 提示词与动作校验"]
    Graph --> Client["OpenAI 兼容模型客户端"]
    Client --> Proxy["本机 LiteLLM Proxy"]
    Proxy --> Model["已授权上游模型，默认 Agnes"]
    Graph --> Trace["OpenTelemetry 本地轨迹"]
    DB --> Packet["版本化诊断包"]
    Trace --> Packet
    Packet --> External["仓库外的评审 agent, 不在进程内"]
```

前端与 API、执行器分开，是为了让外部请求和模型延迟不占用页面。任务写入 SQLite。执行器一次处理一个任务。paper agent 是唯一的 Agent 角色，模型调用可以多次。仓库外的评审 agent 不自由搜索，也不改任务目标。首版没有账户服务，也没有分布式队列。组件取舍见 [技术选型](tech-stack.md)。

## 代码布局

**规则**：实现时按下面的目录划分模块。不要把接口、图谱节点、来源连接器和测试放进同一个包。

- `frontend/`：作者界面。不保存密钥，不写判断规则。
- `backend/paper_evidence/domain/`：结果标签、任务状态、错误码、诊断包模型。无网络，无数据库。
- `backend/paper_evidence/storage/`：SQLite 与 FTS5。
- `backend/paper_evidence/sources/`：Crossref、PMC、OpenAlex。只读官方端点，不调用模型。
- `backend/paper_evidence/retrieval/`：当前文献的切分与检索。
- `backend/paper_evidence/agents/`：只放 paper agent 的提示词和输出结构校验。不能自己发 HTTP，也不能读本地文件。图谱不编排第二个 agent。
- `backend/paper_evidence/models/`：OpenAI 兼容客户端及网关元数据适配。只连接已配置 Proxy，关闭客户端重试，不直连供应商。
- `backend/paper_evidence/graph/`：LangGraph 节点。编排来源、检索、模型客户端，验证动作和预算；网络由连接器及客户端执行。
- `backend/paper_evidence/diagnosis/`：从任务记录投影诊断包，并做脱敏。不自动改任务，也不充当路径二的测试产品。
- `backend/paper_evidence/tracing/`：本地 OpenTelemetry。
- `backend/paper_evidence/api/`：运行配置预览、只读来源解析、任务入队/查询、反馈/删除和诊断包导出；不运行核验图谱。
- `backend/paper_evidence/worker/`：一次运行一个任务。
- `tests/`：按 [测试方案](test-plan.md) 的维度分目录，包括 `functional/`、`tools/`、`retrieval/`、`session/`、`adversarial/`、`boundary/`、`performance/` 和 `e2e/`。
- `eval/`：若放置研究数据，只给研究评测使用。运行时包不得导入它。

```mermaid
flowchart TD
  frontend[frontend]
  api[api]
  worker[worker]
  graphPkg[graph]
  domain[domain]
  sources[sources]
  retrieval[retrieval]
  agents[agents]
  diagnosis[diagnosis]
  storage[storage]
  tracing[tracing]
  frontend --> api
  api --> domain
  api --> storage
  api --> sources
  api --> diagnosis
  worker --> storage
  worker --> graphPkg
  graphPkg --> domain
  graphPkg --> sources
  graphPkg --> retrieval
  graphPkg --> agents
  graphPkg --> models[models]
  models --> proxy[LiteLLM Proxy]
  graphPkg --> diagnosis
  graphPkg --> storage
  graphPkg --> tracing
  diagnosis --> storage
```

**规则**：界面只调用 API。API 不进入图谱节点。API 可调用只读来源解析与诊断投影。图谱可以调用领域、来源、检索、Agent、模型客户端、诊断、存储和轨迹。Agent 与来源互不调用。诊断可以读存储以投影诊断包，但不能改任务状态。

来源和许可由 sources 提供，切分/FTS5/邻居读取由 retrieval 与 storage 完成；agents 只构造提示词及校验结构；graph 验证动作范围、编排 models 调用并保存阶段结果。diagnosis 从本地记录投影版本化诊断包，不运行第二名 Agent。

## 2. 执行流程与状态

状态定义见 [任务状态](glossary.md#2-任务状态)。下图里的终态名称与该表一致。

```mermaid
stateDiagram-v2
    [*] --> QUEUED
    QUEUED --> RUNNING
    RUNNING --> COMPLETED
    RUNNING --> BLOCKED
    RUNNING --> FAILED
    RUNNING --> INTERRUPTED: 进程重启时遗留的 RUNNING
    COMPLETED --> [*]
    BLOCKED --> [*]
    FAILED --> [*]
    INTERRUPTED --> [*]
```

**规则**：进程启动时，把遗留的 `RUNNING` 标为 `INTERRUPTED`，由作者明确重试。重试不沿上图把终态改回 `QUEUED`。它新建一条 `QUEUED` 任务，并保留原记录，避免静默重复外部调用。

```mermaid
flowchart TD
    A["作者输入论断与 DOI"] --> B["展示书目、接收方与预算"]
    B --> C{"确认来源与运行配置?"}
    C -- "否" --> Stop["停止，不创建任务"]
    C -- "是" --> Q["QUEUED → RUNNING"]
    Q --> S{"身份、来源、许可与完整性通过?"}
    S -- "否" --> Block["BLOCKED + 无法核验来源"]
    S -- "是" --> G["请求 1: 生成文献语言检索词"]
    G --> R["初始 FTS5 检索"]
    R --> D["请求 2: 判断或申请补充检索/补读"]
    D -- "提交判断" --> V{"结构、来源、摘录有效?"}
    D -- "补充动作" --> R2["至多一轮补充检索与邻居读取"]
    R2 --> Empty{"合并候选仍为空?"}
    Empty -- "是" --> Insufficient["证据不足 + RETRIEVAL_EMPTY"]
    Insufficient --> Done
    Empty -- "否" --> D2["请求 3: 最终判断，不再申请补读"]
    D2 --> V
    V -- "是" --> Done["COMPLETED + 结果标签"]
    V -- "否且修复可用" --> Fix["全任务最多一次输出修复"]
    Fix --> V2{"重新校验通过?"}
    V2 -- "是" --> Done
    V2 -- "否" --> Fail["FAILED，学术标签为空"]
    V -- "否且修复用尽" --> Fail
```

图示为正常与最终输出校验路径。每次请求（包括查询生成和中间动作）也检查结构；网络失败、非法动作、预算越界按下表处理，不能跳过这些出口。第一次检索为空时，请求 2 必须申请补充查询，不能直接以检索为空结束；不符合该动作约束时按输出校验处理。对无法独立判断的多主张输入，最终只能说明歧义并提示拆分，不输出确定判断。完成补充检索后无候选可直接生成「证据不足」及 `RETRIEVAL_EMPTY`，不必消耗请求 3；有候选时由请求 3 提交最终判断。仍有片段但不充分时，模型提交证据不足并说明限制，错误码为 null。

### 动作与预算

**规则**：请求 1 输出文献语言的非空 queries 字符串数组；请求 2 输出 `action=final` 加最终判断，或 `action=retrieve` 加 queries 和 neighbor_paragraph_ids；请求 3 仅能 final。它们都是同一个 paper agent 的不同步骤，不新增内部评审。retrieve 至少提供一个查询或已知邻居段落 ID；初次无候选时必须提供非空 queries。查询生成只发送论断与已确认的书目/文献语言，不发送整篇正文；判断只发送获准候选片段。

- `search(source_id, queries)` 与 `read_neighbors(source_id, paragraph_ids)` 只访问当前任务冻结的来源。source_id 由工作流绑定；模型只提交查询及当前来源已知段落 ID。非法段落 ID、任意 URL/路径等动作输入不执行。
- 初始检索为 round=0；补充查询和邻居读取合并为唯一的 round=1，去重后进入上下文。FTS 查询由程序安全构造，模型文本不能成为 SQL。
- 每任务最多三个主逻辑请求，加一个全局输出修复请求。修复任一阶段后继续原流程，不增加主请求配额，也不重置补读次数。
- 结构、动作字段或摘录错误可以修复一次；修复只得到原请求的已核对材料及校验错误，不增加来源或工具权限。修复仍错则失败，保留两次输出的本地记录与验证结果。
- 请求 3 再要求补读或任何即将超出授权预算的动作，调用前终止为 `BUDGET_EXCEEDED`；不得伪装成证据不足。请求 2 的非法字段则按输出校验处理。
- 每个逻辑请求最多两个实际上游尝试，恢复与回退共用一次机会，故整任务最多八个上游尝试。模型客户端不重试；Proxy 执行 [D6](tech-stack.md#d6-模型适配) 的恢复策略，工作流不能再叠加网络重试。
- 上述次数是初始工程上限，不是最优参数或性能结果。超时和检索上下文上限在实现配置中显式设置并纳入 config_digest；改变配置不能扩大正在执行任务的授权，评测运行冻结该配置。

前置完整性检查发现内容不足时不调用模型；若补读时才发现判断依赖缺失图表，也进入 `CONTENT_INCOMPLETE`，不把缺失内容补成结论。完成检索仍不足属于学术结果；上游故障、无效输出和预算阻断属于执行失败。所有终态都可导出诊断包；外部评审不同意见不回写任务。

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

### `GET /api/run-config`

返回当前配置的 `profile`、`config_digest`、主用/备用接收方、模型别名、数据发送范围和 [limits](glossary.md#6-诊断包)。不返回密钥或私有部署地址。默认 daily；evaluation 由运行配置选择。前端据此展示整次任务授权，不逐次弹窗。

### `POST /api/checks`

| 项 | 内容 |
| --- | --- |
| 请求体 | `claim`、`doi`、`source_confirmed`、`cloud_consent`、`config_digest`、`authorized_recipients` |
| `202` | `id`、`status`=`QUEUED`。入队后返回，不等待模型 |
| `400` | 两个确认字段不是同时为真、输入无效，或授权缺少主接收方。不创建任务、不调用模型 |
| `409` | config_digest 与预览配置不一致；重新预览确认后提交 |
| 约束 | 保存授权与运行配置快照；未授权的备用接收方从本次路由排除，不接受请求体传入任意上游地址 |

### `GET /api/checks`

| 项 | 内容 |
| --- | --- |
| 查询参数 | 可选 `status`，取值见 [任务状态](glossary.md#2-任务状态) |
| `200` | 摘要数组。每项含 `id`、`doi`、`status`、`stage`、`label`。`label` 尚未产生时为 `null` |
| 约束 | 不返回缓存全文 |

### `GET /api/checks/{id}`

| 项 | 内容 |
| --- | --- |
| `200` | `id`、`status`、`stage`、`label`、`error_code`、`decision` |
| `decision` | [最终判断](glossary.md#最终判断) 对象，含多条 evidence、理由、支持部分、范围差异及限制；无有效最终判断时为 null |
| 约束 | `label` 只使用结果标签的前五种。`FAILED` 时 `label` 为 `null`，界面根据状态显示「执行失败」。`BLOCKED` 时 `label` 为「无法核验来源」。paper agent 的标签不冒充真值。响应不含第二名 agent 的意见 |

### `GET /api/checks/{id}/diagnostic-packet`

| 项 | 内容 |
| --- | --- |
| `200` | [输入诊断包](glossary.md#6-诊断包) |
| 约束 | 固定返回 redacted 包，自由文本按术语表遮盖；已授权模型调用不等于授权诊断外传 |

### `POST /api/checks/{id}/diagnostic-export`

请求含 `recipient` 和 `semantic_export_consent=true`。前端先在本地预览拟导出的字段；服务端核对授权及来源使用范围后返回 consented 包并记录接收方，不主动上传。缺少授权返回 400，来源范围不允许则返回 409。完整提示词、原始模型响应、密钥不在导出范围。

### `POST /api/checks/{id}/feedback`

| 项 | 内容 |
| --- | --- |
| 请求体 | `comment` |
| `200` | `id`、`saved`=`true` |
| 约束 | 与 paper agent 的判断分开保存。不是完成任务的前置条件 |

### `POST /api/checks/{id}/retry`

| 项 | 内容 |
| --- | --- |
| `202` | `id`（新任务）、`status`=`QUEUED`、`previous_id` |
| `409` | 原任务不是终态 |
| 请求体 | 当前 `config_digest`、`authorized_recipients`、`cloud_consent`、`source_confirmed` |
| 约束 | 保留原失败或原结果记录；重新确认当前配置，使用与创建任务相同的输入/授权校验，失败返回 400 或 409 |

### `DELETE /api/checks/{id}`

| 项 | 内容 |
| --- | --- |
| `200` | `id`、`deleted`=`true`、`message`（说明不能撤回云端数据） |
| `409` | 任务不是终态 |
| 约束 | 只删除本地任务及其关联记录。来源缓存仅在没有其他任务引用时清理 |

## 4. 本地记录与失败处理

**规则**：每条任务至少保存输入 DOI 与 Crossref 元数据、PMCID、所用全文版本与许可、来源 URL、获取时间、内容哈希、paper agent 的标签及限制说明、每个逻辑请求及实际上游尝试的标识、路由、提示词版本与元数据、轨迹 ID。证据项保存章节、JATS 段落标识、逐字摘录与段落哈希。JATS 没有稳定段落标识时，用版本哈希与段落顺序生成本地定位，并标明这种定位的局限。不另存一份内部评审记录。

诊断包是这些记录的 2.0 投影。默认外传包遮盖论断及可能泄漏论断的所有自由文本，不包含完整提示词、原始模型响应和密钥。投影字段以术语表为准。

失败时的终态映射见 [错误码](glossary.md#4-错误码)，恢复由下表唯一负责：

| 条件 | 负责层、上限及停止行为 |
| --- | --- |
| 身份/来源/许可/完整性阻断 | sources 提供原因，graph 停止；不替换文献、不调用模型补结论 |
| 初次检索为空 | graph 允许 paper agent 发起一次补充检索；仍为空才 RETRIEVAL_EMPTY |
| 输出结构或摘录无效 | graph 组织一次全局修复，重新确定性校验；再失败按实际原因停止 |
| 模型连接故障、超时、限流、暂时性服务错误 | Proxy 最多一次恢复，原部署或已授权备用部署二选一；仍失败返回独立错误码 |
| 模型认证/参数错误 | 客户端与 Proxy 均不重试，不自动改写参数静默降级 |
| 来源请求的短暂故障 | sources 最多重试一次，遵守 Retry-After；恢复仍失败时 FAILED，不能伪装成 SOURCE_UNAVAILABLE |
| 超出模型或补读预算 | graph 在发起前拒绝，BUDGET_EXCEEDED；不以修复名义继续调用 |

**规则**：论文、网页和接口返回都是不可信数据，其中的指令不予执行。文献连接器只访问官方只读端点，并限制超时、重试次数和请求频率。

**规则**：SQLite 和获许可的缓存只放在本地，并排除出 Git。OpenTelemetry span 记录任务 ID、DOI 哈希或规范标识、来源版本哈希、候选段落 ID 与数量、阶段、工具名、耗时、错误码和 token 数。应用与 Proxy 的日志/span 不记录论断原句、全文、查询、提示词、原始响应或密钥；异常载荷也须脱敏。Proxy 的逐次元数据回调与本地轨迹用 request_id 关联，响应 model 字段不能冒充真实版本，缺失 usage 用 null。完整语义诊断包只在本地生成。若交给仓库外的评审 agent，之前要预览字段、遵守来源许可，并取得作者对未发表论断的单独同意。用户核验本身不发起这次外传。实验用的输入和来源快照放在访问受控的本地数据集中，并另存版本标识。

轨迹说明哪一步观察到什么输入、输出或错误。它不能证明模型内部如何推理。受控故障的真因由隐藏的注入记录确定。自然样本中的争议需要独立标注，不能只凭 span 名称或 Agent 自述下结论。[OpenTelemetry 手动埋点](https://opentelemetry.io/docs/languages/python/instrumentation/)

## 5. 后续扩展接口

**排除**：整篇论文模式不是首版能力。以后若做，先抽取“引文句与参考文献”的候选对应，再请作者确认有歧义的映射，然后拆成现有的单条核验任务。PDF 解析的取舍见 [D10](tech-stack.md#d10-暂不采用)。
