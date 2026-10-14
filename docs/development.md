# 开发指南

本文说明当前项目骨架的运行方式与接口边界。产品目标和未来行为以[产品需求](prd.md)、[架构设计](architecture.md)及[术语表](glossary.md)为准。

## 项目结构

| 目录 | 用途 |
| --- | --- |
| `backend/paper_evidence/domain/` | 任务状态、标签、错误码和请求/响应类型；规范 JSON 摘要、文本与定位契约和判据快照。不执行网络或数据库操作。 |
| `backend/paper_evidence/api/` | FastAPI 健康检查、运行配置预览、只读来源解析和任务路由；不运行核验图谱。 |
| `backend/paper_evidence/*/ports.py` | 来源、存储、检索、模型、工作流、诊断、轨迹和 worker 的类型化模块接口。 |
| `frontend/src/` | Vue 静态页面和 API 客户端类型声明。 |
| `tests/tools/`、`tests/boundary/`、`tests/retrieval/`、`tests/session/` | HTTP 接口与契约、领域规则与存储生命周期、检索与切分、有界工作流的检查。 |

模块调用关系见[架构设计](architecture.md#代码布局)。`Protocol` 声明不能实例化，具体适配器在 `storage/sqlite.py`、`sources/`、`retrieval/`、`models/`、`agents/`、`graph/`、`diagnosis/`、`tracing/` 和 `worker/` 中实现。SQLite/FTS5、来源连接器、模型传输和有界流程已接入；LangGraph 编排改为等价的显式状态机（`graph/workflow.py`），Langfuse 导出尚未接入。

存储、检索、提示词和轨迹端口是同步接口。异步 worker 通过 `asyncio.to_thread` 调用它们，不在事件循环上直接执行 SQLite 或 FTS5。来源、模型和工作流的进程内 `deadline` 是 `time.monotonic()` 的绝对时刻；写入任务的 `claimed_at`/`deadline_at` 用墙钟 UTC 秒，因为这两个值会由 API 进程读取，进程内单调时钟跨重启没有意义。

检索的 `read_neighbors(source_id, paragraph_ids)` 返回给定段落及其 `ordinal±1` 相邻段落，范围仍限于当前任务的冻结来源；`search` 与 `read_neighbors` 都只接受工作流绑定的 `source_id`，跨来源段落 ID 只会解析为空。PMC OAI-PMH 的 XML 用标准库 `xml.etree.ElementTree`（CPython 的 expat）解析，不引入第三方 XML 依赖；该解析器的实体膨胀限制是安全前提，升级 Python 或更换解析器时须重新确认。

## 本地环境

安装与启动命令见 [README](../README.md)。命令示例使用 Bash；如果 `python3.12` 不在 PATH，可将其替换为 Python 3.12 解释器的绝对路径。环境目录、依赖目录和构建产物由 `.gitignore` 排除。

后端使用 `requirements.lock` 安装已锁定的运行、测试和构建依赖，再以 `--no-deps --no-build-isolation` 安装本地 editable 包。修改依赖时须同步 `pyproject.toml` 与锁定文件；前端依赖通过 `npm ci` 安装。

## HTTP 接口

`GET /health` 返回 `200` 和 `{"status":"ok"}`，仅表示 API 进程可响应请求。

架构文档中的 13 个业务接口均已实现，其中 `GET /api/checks/{id}/input` 与 `GET /api/checks/{id}/evidence-context` 是两个只读投影。符合请求类型的调用不再返回占位的 `501`；骨架期的 `501` OpenAPI 声明和带 `scaffold` 标记的断言已随实现移除。任务路由只读写本地存储、在 API 边界做输入与授权校验并映射领域错误，不运行核验图谱；`POST /api/checks` 入队后立即返回 `202`，不等待模型。

来源预览的 `ContractError` 映射由全局处理器完成，其余路由在各自边界把领域失败映射为 `ApiError` 或 `ConflictResponse`，因此业务 `422` 与请求校验 `422` 可区分。`GET /api/run-config` 返回的 `config_digest` 来自冻结的有效配置快照；`POST /api/checks` 只接受与该摘要（或其收窄后的授权范围）一致的请求，否则返回 `409`。

两个只读投影只读本地记录与该任务的冻结来源，不调用来源连接器或模型，也不改变任务。`GET /api/checks/{id}/input` 返回提交时的原始输入，是一条**按任务**的直接读取、不依赖历史列表是否已加载；它另外给出该任务**冻结**的 `config_digest` 与 `authorized_recipients`——这两个是冻结值，**不是**重提时应发送的摘要：`POST /api/checks` 校验的是**当前**有效摘要，只有有效配置未变时冻结值才被接受，否则返回 409。任务详情只在 `source` 中给 DOI，而来源身份解析成功前 `source` 为 null，所以详情视图本身在该阶段没有 DOI；但 `CheckSummary` 也带 `doi`，工作台目前就是从历史行回退取值，本接口不是取得该 DOI 的唯一路径。`GET /api/checks/{id}/evidence-context` 返回进入模型上下文的候选段落与最终判断引用的段落，各自按 `ordinal±1` 展开为邻段并按段落序号升序返回；`text` 是冻结段落原文而不是已发布的 quote，邻段只作上下文、不作为证据，所以不带 `validation`。段落取自获许可的本地冻结版本：脱敏诊断包把 quote 换成占位符，本接口保留原文供作者在本机核对引用。来源未冻结时 `source_id` 为 null、`paragraphs` 为空；来源已冻结但尚无候选或引用（如任务在 `query_generation` 阶段失败）时 `source_id` 有值而 `paragraphs` 为空。真实 PMC 来源经 `pmc_fm` 取回的内容目前不含正文（`<body>` 计数为 0，见 #28），此时 `ordinal±1` 的邻段展开为空，本接口只能返回锚点自身。

请求缺字段或不符合请求模型时返回 `422`，响应体为 `ApiError`：error_code=null，message 形如「请求不合法：body.claim: missing」。只公开已声明字段的路径、数组/JSON 位置和错误类型，不回显输入值、未知字段名或原始校验上下文。未知路径和不允许的方法也使用同一形状及中文固定文案；405 保留框架提供的 Allow 等响应头。

框架级错误使用 `HTTPException`，error_code=null；业务错误不使用结构化 `HTTPException`，而是在 API 边界映射 `ContractError`。来源预览已声明 DOI_INVALID→400、DOI_UNRESOLVABLE→404、METADATA_NOT_FOUND/REGISTRATION_AGENCY_UNSUPPORTED→422，及 sources 端口规定的 UPSTREAM 分类→502/503/504。映射保留真实 error_code，文案使用本地固定文本，不回显底层异常载荷；由此可区分业务 422 和请求校验 422。其他端点或未定义错误不借用这个预览映射，也不套用相近业务码。错误使用结构化 HTTPException 时记录脱敏结构摘要（类型、项数及已知错误码），不记录原始键名/值。DOI、授权、预算和任务状态等业务校验在 API 边界完成，涉及来源的调用经 `sources/` 连接器访问官方只读端点。

创建任务的配置摘要冲突使用不含任务状态的 ApiError；已有任务的状态冲突使用 status/stage 必填的 ConflictResponse。default_limits()/default_timeouts() 提供术语表规定的默认配置，每次返回独立实例；具体任务仍须保存实际配置并纳入 config_digest。

OpenAPI 声明了预期的成功响应类型和架构中已写明的错误响应。诊断包类型声明遵循 schema `2.2`；`redacted` 与 `consented` 投影在 `diagnosis/projector.py` 中实现，配置摘要和判据快照分别由 `config.py` 与 `domain/rules.py` 生成。脱敏包保留公开书目字段并在预览中明确该边界。

前端只定义 API 客户端类型，没有 HTTP 客户端实现；静态页面不会提交任务或生成模拟结果。

`POST /api/checks` 与 `POST /api/checks/{id}/retry` 的 `authorized_recipients` 必须是已配置接收方（主接收方加 `PAPER_EVIDENCE_FALLBACK_RECIPIENTS`）的子集，越界返回 `400`；范围内的名单只能收窄，收窄后的授权随其摘要写入任务快照，不会扩大预览范围。诊断导出不复用模型接收方：`recipient` 必须等于运行配置里的已授权观测/诊断接收方，否则返回 `400`；该标识由 `PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT`（兼容旧名 `PAPER_EVIDENCE_LANGFUSE_RECIPIENT`）配置，未配置时不产生 `consented` 导出。来源使用范围不允许时仍返回 `409`。

## Worker 入口

从仓库根目录执行：

```bash
backend/.venv/bin/python -m paper_evidence.worker            # 处理完当前队列后退出
backend/.venv/bin/python -m paper_evidence.worker --loop     # 常驻，持续领取新任务
```

默认一次性模式先结算遗留 `RUNNING`，再逐个领取并执行已排队任务，队列为空时退出，退出码 `0`。单条任务的执行时限从领取并转为 `RUNNING` 起算。

结算只处理**可证已死**的遗留行：该行的 `deadline_at` 已过，或没有 `deadline_at`（领取路径一定会写入，缺它就不可能是活着的领取）。有取消标记的转为 `CANCELLED`，其余转为 `INTERRUPTED`。仍在时限内的 `RUNNING` 行不是孤儿，其所属进程可能正在执行，结算不动它。

**同一时刻只执行一个任务**有两层保证。第一层是运行约定：只启动一个 worker。第二层是存储层不变量：只要有任务处于 `RUNNING`，`SqliteStore.claim_next` 就拒绝领取（返回 `None`），第二个 worker 因此拿不到下一条任务，也不会与在途任务并行执行。约定仍然有效，但误起第二个 worker 已不再是「无防护」：它抢不走任务，启动结算也不会把在途任务翻成 `INTERRUPTED`（Issue #34）。

结算不只在进程启动时做一次：崩溃遗留的行在重启那一刻通常还没到 `deadline_at`，只结算一次会让队列一直卡住。`run_once` 每轮领取前都会结算，队列在 deadline 到点后的一个轮询间隔内恢复。

`--loop`（等价环境变量 `PAPER_EVIDENCE_WORKER_LOOP=1`）改为常驻：先把队列排空，再按间隔轮询新任务，直到进程收到中断信号。轮询间隔用 `--interval <秒>` 或 `PAPER_EVIDENCE_WORKER_POLL_SECONDS` 设置，默认 `1.0` 秒，下限 `0.05` 秒（更小的值按 `0.05` 处理）。前端始终以 1.5 秒轮询任务详情，因此需要 API 与常驻 worker 同时运行，排队任务才会进入 `RUNNING`；只跑一次性 worker 时，任务入队后会一直停在 `QUEUED`。API 进程本身不执行任务。

常驻循环对单个任务的失败是隔离的。`run_once` 先结算可证已死的遗留行，再领取并记账；构造工作流和运行工作流都在同一个兜底里：工作流抛出的异常落为该任务的 `FAILED`（error_code 为 null，worker 的未分类分支），而不是让循环中断。工厂或存储层抛出的异常由循环自身捕获、记录后继续下一轮；这类任务留给遗留 `RUNNING` 结算（其 deadline 到点后的下一轮，或下次进程启动），不由这一层冒充终态。`asyncio.CancelledError` 继承自 `BaseException`，不被这条兜底吞掉，停止路径照常退出。

已受理的取消优先于完成或失败结果：工作流在写入终态前复查取消标记，`SqliteStore.finish` 也在同一事务内拒绝非 `CANCELLED` 的终态写入到 `cancel_requested = 1` 的任务，随后由取消路径落 `CANCELLED`。取消检查点与终态写入之间的窗口因此不跨进程内竞争：取消已受理时任务最终显示为「已取消」，而不是「已完成」。

任务详情返回 `created_at`、`started_at`、`finished_at` 三个时刻：入队时写 `created_at`，worker 领取并转 `RUNNING` 时写 `started_at`，终态（含取消、超时与遗留任务结算）落定写入 `finished_at`。`updated_at` 与 `finished_at` 在同一次写入里取同一个时刻，因此「最后更新」不会晚于「结束」。仍在 `QUEUED` 的任务没有 `started_at`，未终结的任务没有 `finished_at`；前端把缺失的一端显示为未知，不估算用时。历史列表按 `created_at` 倒序返回，前端按服务端顺序渲染。

数据目录由 `PAPER_EVIDENCE_DATA_DIR` 指定，默认是当前工作目录下的 `.paper-evidence/`；已授权的观测/诊断接收方由 `PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT` 配置，默认没有，未配置时无法导出 `consented` 诊断包。

模型传输由 `PAPER_EVIDENCE_MODEL_TRANSPORT` 选择，默认 `sdk`：LiteLLM 以库的形式在 API/worker 进程内运行，上游凭据从 `PAPER_EVIDENCE_MODEL_API_KEY` 读取，上游地址可用 `PAPER_EVIDENCE_MODEL_API_BASE` 覆盖，要调用的模型由 `PAPER_EVIDENCE_PROVIDER_MODEL` 指定（默认 `openai/agnes-2.5-flash`），业务代码仍只用别名 `paper-default`。取值为 `gateway` 时改走 OpenAI 兼容客户端连接 `PAPER_EVIDENCE_MODEL_BASE_URL` 指定的本机 Proxy，凭据从 `PAPER_EVIDENCE_GATEWAY_TOKEN` 读取，上游地址与密钥留在 Proxy 一侧。未知取值回落到默认；生效的传输方式与端点类别写入冻结配置快照并计入 `config_digest`，因此预览显示的形态与实际调用一致。两种形态都不把密钥写入配置摘要或日志。

要真的跑一次核验，最小模型配置只有一项：在**运行 worker 的那个进程**里提供 `PAPER_EVIDENCE_MODEL_API_KEY`。应用不读取 `.env` 文件，配置只来自进程环境，所以要在启动命令的环境里给出（或在服务管理器里配置）：

```bash
# 最小集：一个密钥即可；API 进程（uvicorn）不调用模型，不需要这一项
PAPER_EVIDENCE_MODEL_API_KEY=sk-... backend/.venv/bin/python -m paper_evidence.worker --loop
```

需要换模型时加 `PAPER_EVIDENCE_PROVIDER_MODEL`（LiteLLM 的「供应商/模型」写法，如 `openai/gpt-4o-mini`）；只有上游不是该供应商的默认端点时才需要 `PAPER_EVIDENCE_MODEL_API_BASE`（如 `https://your-endpoint/v1`）。凭据缺失或端点不可达时，任务在 `query_generation` 阶段以映射后的 `UPSTREAM_*` 错误码结束，不会回落到任何内置模型、本地替身或模拟数据。诊断导出另需 `PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT`，与模型凭据无关。

`litellm` 是运行时必需依赖，导入时默认会下载远程价目表；本项目把费用记为未知，因此在导入 LiteLLM 之前设 `LITELLM_LOCAL_MODEL_COST_MAP=True`，跳过这次网络请求。

## 检查范围

检查环境需安装后端锁定依赖，并先运行 `npm --prefix frontend ci`；pytest 的前后端契约检查通过 Node.js 调用已有 TypeScript 编译器，未安装 Node.js 或前端依赖时会明确失败——具体表现为 `tests/boundary/test_frontend_shapes.py` 的用例整组失败（检查器 `inspect-contracts.mjs` 找不到 `typescript` 模块），与业务改动无关，先补前端依赖即可。

README 中的检查验证接口表面、领域枚举及默认配置与文档的一致性、摘要与文本契约、检索与切分、有界工作流的预算与出口、来源与模型传输的错误映射、模块导入和前端构建。响应状态表从架构文档解析并与 OpenAPI 双向比较（不再放宽 `501`）；前端命名接口与所有 OpenAPI 对象模型比对字段、必填性和可空性（含继承及 Omit）。客户端方法接口不属于 JSON 对象契约。HTTP 与任务测试使用临时数据目录和合成请求；上游连接器与 Proxy 形态的模型传输用 `httpx.MockTransport` 覆盖状态映射，不访问真实网络；SDK 形态的传输用注入的完成函数覆盖错误映射与恢复，另有两条用例经真实 `litellm.acompletion` 加 `mock_response` 走通 SDK 入口。

这些检查不替代真实来源、模型接入、任务执行或论文语义验收；已实现模块的单元与桩测试通过，不代表真实 Crossref/PMC/OpenAlex/Proxy 连通性或论文语义结论已验证。每次 PR 应在说明中记录实际运行的命令、结果和未覆盖范围；团队协作及独立评审要求见 [AGENTS.md](../AGENTS.md)。
