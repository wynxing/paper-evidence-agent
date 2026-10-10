# Paper Evidence Agent

Paper Evidence Agent 旨在核对单条论断与指定被引文献之间的证据关系，并提供可定位的原文依据。目标用户是在投稿前复查引文的生物医学论文作者。

项目采用传智杯[「AI赋能·智能测试创新挑战赛」](https://www.boxuegu.com/matchTrack/detail/?id=10041)路径一：本仓库实现 paper agent，评审由仓库外的成熟 agent 完成。

## 当前状态

后端已实现首版业务流程，前端仍为静态页面：

- FastAPI 后端可启动，`GET /health` 返回 `200`；运行配置预览、只读来源解析、任务创建/查询/取消/重试/反馈/删除和诊断包接口均为实现代码，不再返回 `501`。
- 任务写入本地 SQLite + FTS5；来源解析按 Crossref、PMC ID 转换、PMC OAI-PMH 顺序核对身份、许可与语言，只自动处理许可为 CC0 或 CC BY 的英文 JATS 正文。
- 模型调用经 OpenAI 兼容客户端发往本机 LiteLLM Proxy，客户端不重试；核验流程按有界预算执行查询生成、检索、判断、至多一轮补读和一次全局输出修复。
- Vue 前端仍提供静态页面，显示“功能待实现”，输入和操作按钮禁用。

尚未验证或未实现：真实 Crossref/PMC/OpenAlex/Proxy 连通性、论文语义验收、LangGraph 编排（当前以等价的显式状态机实现）、Langfuse 导出、Playwright 端到端用例。设计文档描述目标行为，不能作为能力已完成或语义验收通过的依据。

## 环境要求

- Python 必须使用 3.12（当前后端要求 `>=3.12,<3.13`）
- Node.js 22.12 或更高版本、npm

依赖分别锁定在 [`backend/requirements.lock`](backend/requirements.lock) 和 [`frontend/package-lock.json`](frontend/package-lock.json)。启动后端、查看配置和运行后端测试不需要模型密钥；执行核验任务需要按 [D6](docs/tech-stack.md#d6-模型适配) 配置本机 LiteLLM Proxy，并通过 `PAPER_EVIDENCE_GATEWAY_TOKEN` 提供网关访问凭据。

## 快速开始

在一个终端中，从仓库根目录启动后端：

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m uvicorn paper_evidence.api.app:app --host 127.0.0.1 --port 8000
```

后端地址：<http://127.0.0.1:8000>。健康检查为 `/health`，接口声明为 `/docs`。

在另一个终端中，从仓库根目录启动前端：

```bash
cd frontend
npm ci
npm run dev
```

前端默认地址：<http://127.0.0.1:5173>。两个服务默认均绑定本机回环地址。Windows 在 `backend` 目录使用 `.\.venv\Scripts\python` 代替 `.venv/bin/python`，其余参数相同。

## 开发检查

从仓库根目录执行：

```bash
npm --prefix frontend ci
backend/.venv/bin/python -m pytest -c backend/pyproject.toml
backend/.venv/bin/python -m pip check
npm --prefix frontend run build
```

pytest 的前后端契约检查需要 Node.js 和已安装的前端依赖。前端构建包含 TypeScript 类型检查。接口占位行为、模块边界和 worker 入口说明见[开发指南](docs/development.md)。

## 持续集成

拉取请求和推送到 `main` 会运行两个检查：`backend` 执行 pytest，`frontend` 执行前端构建。

本地从仓库根目录复现：`npm --prefix frontend ci`，`backend/.venv/bin/python -m pytest -c backend/pyproject.toml`，`npm --prefix frontend run build`。

## 文档

- [产品需求](docs/prd.md)
- [术语表与数据契约](docs/glossary.md)
- [架构设计](docs/architecture.md)
- [测试方案](docs/test-plan.md)
- [技术选型](docs/tech-stack.md)
- [开发指南](docs/development.md)
- [决策记录](docs/decisions.md)
- [验证记录](docs/verification.md)
- [协作规范](AGENTS.md)

[研究评测](docs/evaluation.md)属于后续研究，运行时代码不得依赖其中的数据集。
