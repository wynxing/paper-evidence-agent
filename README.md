# Paper Evidence Agent

Paper Evidence Agent 旨在核对单条论断与指定被引文献之间的证据关系，并提供可定位的原文依据。目标用户是在投稿前复查引文的生物医学论文作者。

项目采用传智杯[「AI赋能·智能测试创新挑战赛」](https://www.boxuegu.com/matchTrack/detail/?id=10041)路径一：本仓库实现 paper agent，评审由仓库外的成熟 agent 完成。

## 当前状态

项目处于骨架阶段：

- FastAPI 后端可启动，`GET /health` 返回 `200`；业务接口已声明类型，当前返回 `501 Not Implemented`。
- Vue 前端提供静态页面，显示“功能待实现”，输入和操作按钮禁用。
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

推送到 `main` 以及拉取请求会运行两个检查，名称是 `backend` 和 `frontend`。

- `backend`：使用 Python 3.12，按锁定文件安装后端依赖，再以 `--no-deps --no-build-isolation` 安装本地包，然后运行完整 pytest。契约检查会调用已安装的 TypeScript 编译器，因此该作业也会用 Node.js 执行 `npm --prefix frontend ci`。
- `frontend`：使用 Node.js 22，执行 `npm --prefix frontend ci`，再执行 `npm --prefix frontend run build`（vue-tsc 与 Vite）。`frontend/package.json` 目前没有 `test` 脚本，该作业只做构建。

这些检查不调用真实模型或来源接口。安装前端锁定依赖时，npm 会报告 1 个高危漏洞；本次没有因此改动依赖版本。

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
