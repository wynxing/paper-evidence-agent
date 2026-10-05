# 开发指南

本文说明当前项目骨架的运行方式与接口边界。产品目标和未来行为以[产品需求](prd.md)、[架构设计](architecture.md)及[术语表](glossary.md)为准。

## 项目结构

| 目录 | 用途 |
| --- | --- |
| `backend/paper_evidence/domain/` | 任务状态、标签、错误码和请求/响应类型；不执行网络或数据库操作。 |
| `backend/paper_evidence/api/` | FastAPI 健康检查和业务路由占位。 |
| `backend/paper_evidence/*/ports.py` | 来源、存储、检索、模型、工作流、诊断、轨迹和 worker 的类型化模块接口。 |
| `frontend/src/` | Vue 核验工作台、任务状态管理、真实 HTTP 与显式模拟客户端；公共 API 类型声明保持与后端一致。 |
| `tests/tools/`、`tests/boundary/` | HTTP 接口占位、文档契约和模块导入检查。 |

模块调用关系见[架构设计](architecture.md#代码布局)。`Protocol` 声明不能实例化，当前没有适配器或业务实现。LangGraph、LiteLLM Proxy、SQLite/FTS5 和遥测接入由后续实现任务完成。

存储、检索、提示词和轨迹端口是同步接口。异步 worker 通过 `asyncio.to_thread` 调用它们，不在事件循环上直接执行 SQLite 或 FTS5。来源、模型和工作流的 `deadline` 是 `time.monotonic()` 的绝对时刻。

## 本地环境

安装与启动命令见 [README](../README.md)。命令示例使用 Bash；如果 `python3.12` 不在 PATH，可将其替换为 Python 3.12 解释器的绝对路径。环境目录、依赖目录和构建产物由 `.gitignore` 排除。

后端使用 `requirements.lock` 安装已锁定的运行、测试和构建依赖，再以 `--no-deps --no-build-isolation` 安装本地 editable 包。修改依赖时须同步 `pyproject.toml` 与锁定文件；前端依赖通过 `npm ci` 安装。

## HTTP 接口占位

`GET /health` 返回 `200` 和 `{"status":"ok"}`，仅表示 API 进程可响应请求。

架构文档中的 11 个业务接口均已注册。符合请求类型的调用返回：

```json
{"error_code": null, "message": "Not Implemented：功能待实现"}
```

HTTP 状态为 `501`。这些路由不创建任务、不访问来源或模型，也不生成学术判断。`501` 是骨架期临时契约：实现对应路由时，移除该状态的 OpenAPI 声明和带 `scaffold` 标记的断言。

请求缺字段或不符合请求模型时返回 `422`，响应体为 `ApiError`：error_code=null，message 形如「请求不合法：body.claim: missing」。只公开已声明字段的路径、数组/JSON 位置和错误类型，不回显输入值、未知字段名或原始校验上下文。未知路径和不允许的方法也使用同一形状及中文固定文案；405 保留框架提供的 Allow 等响应头。

框架级错误使用 `HTTPException`，error_code=null；业务错误不使用结构化 `HTTPException`，而是在 API 边界映射 `ContractError`。来源预览已声明 DOI_INVALID→400、DOI_UNRESOLVABLE→404、METADATA_NOT_FOUND/REGISTRATION_AGENCY_UNSUPPORTED→422，及 sources 端口规定的 UPSTREAM 分类→502/503/504。映射保留真实 error_code，文案使用本地固定文本，不回显底层异常载荷；由此可区分业务 422 和请求校验 422。其他端点或未定义错误不借用这个预览映射，也不套用相近业务码。错误使用结构化 HTTPException 时记录脱敏结构摘要（类型、项数及已知错误码），不记录原始键名/值。DOI、授权、预算和任务状态等业务校验及来源调用尚未实现。

创建任务的配置摘要冲突使用不含任务状态的 ApiError；已有任务的状态冲突使用 status/stage 必填的 ConflictResponse。default_limits()/default_timeouts() 提供术语表规定的默认配置，每次返回独立实例；具体任务仍须保存实际配置并纳入 config_digest。

OpenAPI 声明了预期的成功响应类型和架构中已写明的错误响应，但当前路由没有成功实现。诊断包类型声明遵循 schema `2.2`，不代表已实现脱敏、证据校验、配置摘要或诊断包生成。

前端已实现 HTTP 客户端与工作台；默认真实模式按契约发起请求，当前收到业务 501 时保留草稿并显示功能尚未实现。`dev:demo` 显式启用只存于内存的构造数据，不请求后端、来源或模型。交互、接口缺口与验证范围见[前端工作台指南](frontend-workbench.md)。

## Worker 入口

从仓库根目录执行：

```bash
backend/.venv/bin/python -m paper_evidence.worker
```

入口输出待实现说明，并以退出码 `2` 结束，不领取或执行任务。

## 检查范围

检查环境需安装后端锁定依赖，并先运行 `npm --prefix frontend ci`；pytest 的前后端契约检查通过 Node.js 调用已有 TypeScript 编译器，未安装 Node.js 或前端依赖时会明确失败。

README 中的检查验证接口表面、501 占位行为、领域枚举及默认配置与文档的一致性、模块导入和前端构建。响应状态表从架构文档解析并与 OpenAPI 双向比较；前端命名接口与所有 OpenAPI 对象模型比对字段、必填性和可空性（含继承及 Omit）。客户端方法接口不属于 JSON 对象契约。HTTP 测试使用合成请求，并禁用 `socket.create_connection`、`socket.getaddrinfo` 与 SQLite 连接。临时目录为空只说明相对路径没有落盘。

这些检查不替代真实来源、模型接入、任务执行或论文语义验收。每次 PR 应在说明中记录实际运行的命令、结果和未覆盖范围；团队协作及独立评审要求见 [AGENTS.md](../AGENTS.md)。
