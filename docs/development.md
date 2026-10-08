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

模块调用关系见[架构设计](architecture.md#代码布局)。`Protocol` 声明不能实例化，具体适配器在 `storage/sqlite.py`、`sources/`、`retrieval/`、`models/`、`agents/`、`graph/`、`diagnosis/`、`tracing/` 和 `worker/` 中实现。SQLite/FTS5、来源连接器、模型网关和有界流程已接入；LangGraph 编排改为等价的显式状态机（`graph/workflow.py`），Langfuse 导出尚未接入。

存储、检索、提示词和轨迹端口是同步接口。异步 worker 通过 `asyncio.to_thread` 调用它们，不在事件循环上直接执行 SQLite 或 FTS5。来源、模型和工作流的进程内 `deadline` 是 `time.monotonic()` 的绝对时刻；写入任务的 `claimed_at`/`deadline_at` 用墙钟 UTC 秒，因为这两个值会由 API 进程读取，进程内单调时钟跨重启没有意义。

检索的 `read_neighbors(source_id, paragraph_ids)` 返回给定段落及其 `ordinal±1` 相邻段落，范围仍限于当前任务的冻结来源；`search` 与 `read_neighbors` 都只接受工作流绑定的 `source_id`，跨来源段落 ID 只会解析为空。PMC OAI-PMH 的 XML 用标准库 `xml.etree.ElementTree`（CPython 的 expat）解析，不引入第三方 XML 依赖；该解析器的实体膨胀限制是安全前提，升级 Python 或更换解析器时须重新确认。

## 本地环境

安装与启动命令见 [README](../README.md)。命令示例使用 Bash；如果 `python3.12` 不在 PATH，可将其替换为 Python 3.12 解释器的绝对路径。环境目录、依赖目录和构建产物由 `.gitignore` 排除。

后端使用 `requirements.lock` 安装已锁定的运行、测试和构建依赖，再以 `--no-deps --no-build-isolation` 安装本地 editable 包。修改依赖时须同步 `pyproject.toml` 与锁定文件；前端依赖通过 `npm ci` 安装。

## HTTP 接口

`GET /health` 返回 `200` 和 `{"status":"ok"}`，仅表示 API 进程可响应请求。

架构文档中的 11 个业务接口均已实现。符合请求类型的调用不再返回占位的 `501`；骨架期的 `501` OpenAPI 声明和带 `scaffold` 标记的断言已随实现移除。任务路由只读写本地存储、在 API 边界做输入与授权校验并映射领域错误，不运行核验图谱；`POST /api/checks` 入队后立即返回 `202`，不等待模型。

来源预览的 `ContractError` 映射由全局处理器完成，其余路由在各自边界把领域失败映射为 `ApiError` 或 `ConflictResponse`，因此业务 `422` 与请求校验 `422` 可区分。`GET /api/run-config` 返回的 `config_digest` 来自冻结的有效配置快照；`POST /api/checks` 只接受与该摘要（或其收窄后的授权范围）一致的请求，否则返回 `409`。

请求缺字段或不符合请求模型时返回 `422`，响应体为 `ApiError`：error_code=null，message 形如「请求不合法：body.claim: missing」。只公开已声明字段的路径、数组/JSON 位置和错误类型，不回显输入值、未知字段名或原始校验上下文。未知路径和不允许的方法也使用同一形状及中文固定文案；405 保留框架提供的 Allow 等响应头。

框架级错误使用 `HTTPException`，error_code=null；业务错误不使用结构化 `HTTPException`，而是在 API 边界映射 `ContractError`。来源预览已声明 DOI_INVALID→400、DOI_UNRESOLVABLE→404、METADATA_NOT_FOUND/REGISTRATION_AGENCY_UNSUPPORTED→422，及 sources 端口规定的 UPSTREAM 分类→502/503/504。映射保留真实 error_code，文案使用本地固定文本，不回显底层异常载荷；由此可区分业务 422 和请求校验 422。其他端点或未定义错误不借用这个预览映射，也不套用相近业务码。错误使用结构化 HTTPException 时记录脱敏结构摘要（类型、项数及已知错误码），不记录原始键名/值。DOI、授权、预算和任务状态等业务校验在 API 边界完成，涉及来源的调用经 `sources/` 连接器访问官方只读端点。

创建任务的配置摘要冲突使用不含任务状态的 ApiError；已有任务的状态冲突使用 status/stage 必填的 ConflictResponse。default_limits()/default_timeouts() 提供术语表规定的默认配置，每次返回独立实例；具体任务仍须保存实际配置并纳入 config_digest。

OpenAPI 声明了预期的成功响应类型和架构中已写明的错误响应。诊断包类型声明遵循 schema `2.2`；`redacted` 与 `consented` 投影在 `diagnosis/projector.py` 中实现，配置摘要和判据快照分别由 `config.py` 与 `domain/rules.py` 生成。脱敏包保留公开书目字段并在预览中明确该边界。

前端只定义 API 客户端类型，没有 HTTP 客户端实现；静态页面不会提交任务或生成模拟结果。

`POST /api/checks` 与 `POST /api/checks/{id}/retry` 的 `authorized_recipients` 必须是已配置接收方（主接收方加 `PAPER_EVIDENCE_FALLBACK_RECIPIENTS`）的子集，越界返回 `400`；范围内的名单只能收窄，收窄后的授权随其摘要写入任务快照，不会扩大预览范围。诊断导出不复用模型接收方：`recipient` 必须等于运行配置里的已授权观测/诊断接收方，否则返回 `400`；该标识由 `PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT`（兼容旧名 `PAPER_EVIDENCE_LANGFUSE_RECIPIENT`）配置，未配置时不产生 `consented` 导出。来源使用范围不允许时仍返回 `409`。

## Worker 入口

从仓库根目录执行：

```bash
backend/.venv/bin/python -m paper_evidence.worker
```

入口先结算遗留 `RUNNING`（有取消标记的转为 `CANCELLED`，其余转为 `INTERRUPTED`），再逐个领取并执行已排队任务，队列为空时退出，退出码 `0`。单条任务的执行时限从领取并转为 `RUNNING` 起算。

数据目录由 `PAPER_EVIDENCE_DATA_DIR` 指定，默认是当前工作目录下的 `.paper-evidence/`；网关访问凭据从 `PAPER_EVIDENCE_GATEWAY_TOKEN` 读取，只用于本机 Proxy，不写入配置摘要；已授权的观测/诊断接收方由 `PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT` 配置，默认没有，未配置时无法导出 `consented` 诊断包。

## 检查范围

检查环境需安装后端锁定依赖，并先运行 `npm --prefix frontend ci`；pytest 的前后端契约检查通过 Node.js 调用已有 TypeScript 编译器，未安装 Node.js 或前端依赖时会明确失败。

README 中的检查验证接口表面、领域枚举及默认配置与文档的一致性、摘要与文本契约、检索与切分、有界工作流的预算与出口、来源与网关的错误映射、模块导入和前端构建。响应状态表从架构文档解析并与 OpenAPI 双向比较（不再放宽 `501`）；前端命名接口与所有 OpenAPI 对象模型比对字段、必填性和可空性（含继承及 Omit）。客户端方法接口不属于 JSON 对象契约。HTTP 与任务测试使用临时数据目录和合成请求；上游连接器与模型网关用 `httpx.MockTransport` 覆盖状态映射，不访问真实网络。

这些检查不替代真实来源、模型接入、任务执行或论文语义验收；已实现模块的单元与桩测试通过，不代表真实 Crossref/PMC/OpenAlex/Proxy 连通性或论文语义结论已验证。每次 PR 应在说明中记录实际运行的命令、结果和未覆盖范围；团队协作及独立评审要求见 [AGENTS.md](../AGENTS.md)。
