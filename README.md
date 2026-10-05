# Paper Evidence Agent

Paper Evidence Agent 旨在核对单条论断与指定被引文献之间的证据关系，并提供可定位的原文依据。目标用户是在投稿前复查引文的生物医学论文作者。

项目采用传智杯[「AI赋能·智能测试创新挑战赛」](https://www.boxuegu.com/matchTrack/detail/?id=10041)路径一：本仓库实现 paper agent，评审由仓库外的成熟 agent 完成。

## 当前状态

后端处于骨架阶段，前端已提供核验工作台：

- FastAPI 后端可启动，`GET /health` 返回 `200`；业务接口已声明类型，当前返回 `501 Not Implemented`。
- Vue 前端包含新建核验、任务详情、运行诊断，支持显式模拟演示和真实接口模式；真实业务调用仍返回 501，不回退模拟数据。
- 来源解析、持久化、任务执行、模型调用及证据核验尚未实现。

设计文档描述目标行为，不能作为能力已完成或语义验收通过的依据。

## 环境要求

- Python 必须使用 3.12（当前后端要求 `>=3.12,<3.13`）
- Node.js 22.12 或更高版本、npm

依赖分别锁定在 [`backend/requirements.lock`](backend/requirements.lock) 和 [`frontend/package-lock.json`](frontend/package-lock.json)。当前骨架不需要模型密钥。

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

默认 `dev` 为真实接口模式。只预览前端交互时，从仓库根目录执行 `npm --prefix frontend run dev:demo`；该模式无需后端，文献、摘录与结果均为构造数据，不访问文献来源或模型。详细启动、接口缺口和验收进展见[联调 Issue #7](https://github.com/wynxing/paper-evidence-agent/issues/7)。

## 开发检查

从仓库根目录执行：

```bash
npm --prefix frontend ci
backend/.venv/bin/python -m pytest -c backend/pyproject.toml
backend/.venv/bin/python -m pip check
npm --prefix frontend test
npm --prefix frontend run build
```

pytest 的前后端契约检查需要 Node.js 和已安装的前端依赖。前端构建包含 TypeScript 类型检查。接口占位行为、模块边界和 worker 入口说明见[开发指南](docs/development.md)。

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
