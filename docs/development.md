# 开发指南

本文说明当前项目骨架的运行方式与接口边界。产品目标和未来行为以[产品需求](prd.md)、[架构设计](architecture.md)及[术语表](glossary.md)为准。

## 项目结构

| 目录 | 用途 |
| --- | --- |
| `backend/paper_evidence/domain/` | 任务状态、标签、错误码和请求/响应类型；不执行网络或数据库操作。 |
| `backend/paper_evidence/api/` | FastAPI 健康检查和业务路由占位。 |
| `backend/paper_evidence/*/ports.py` | 来源、存储、检索、模型、工作流、诊断、轨迹和 worker 的类型化模块接口。 |
| `frontend/src/` | Vue 静态页面和 API 客户端类型声明。 |
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

请求缺字段或不符合请求模型时返回 `422`，响应体为 `{"error_code": null, "message": "请求不合法"}`。未知路径和不允许的方法也使用同一 `ApiError` 形状，`error_code` 为 null。架构为来源预览规定的 `422` 仍表示 `METADATA_NOT_FOUND` 或 `REGISTRATION_AGENCY_UNSUPPORTED`，与请求不合法共用状态码，靠 `error_code` 区分。DOI、授权、预算和任务状态等业务校验尚未实现。

OpenAPI 声明了预期的成功响应类型和架构中已写明的错误响应，但当前路由没有成功实现。诊断包类型声明遵循 schema `2.2`，不代表已实现脱敏、证据校验、配置摘要或诊断包生成。

前端只定义 API 客户端类型，没有 HTTP 客户端实现；静态页面不会提交任务或生成模拟结果。

## Worker 入口

从仓库根目录执行：

```bash
backend/.venv/bin/python -m paper_evidence.worker
```

入口输出待实现说明，并以退出码 `2` 结束，不领取或执行任务。

## 检查范围

README 中的检查验证接口表面、501 占位行为、领域枚举与文档的一致性、模块导入和前端构建。HTTP 测试使用合成请求，并禁用 `socket.create_connection`、`socket.getaddrinfo` 与 SQLite 连接。临时目录为空只说明相对路径没有落盘。

这些检查不替代真实来源、模型接入、任务执行或论文语义验收。每次 PR 应在说明中记录实际运行的命令、结果和未覆盖范围；团队协作及独立评审要求见 [AGENTS.md](../AGENTS.md)。
