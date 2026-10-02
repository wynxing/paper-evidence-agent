# 验证记录

## 本轮范围

| 项目 | 记录 |
| --- | --- |
| 状态 | 文档修订；用户要求从 PR 中移除文档检查脚本、脚本回归和 GitHub Actions 工作流 |
| 验证对象 | 设计文档提交 9792413 的后续修订；远端分支在本记录更新后核对 |
| 环境 | Windows / PowerShell、Python 3.12.10 |
| 对象 | README 及六份设计/测试 Markdown、决策记录和本验证记录；不含应用实现 |

## 实际检查

| 检查 | 结果 |
| --- | --- |
| `git diff --check` | 本次修订完成后执行；结果见当前 PR 提交记录 |
| 文档链接、示例及契约 | 本轮没有保留可复用的自动检查器。前一临时版本曾运行一次性静态检查及检查器回归，但对应脚本和工作流按用户要求移除；其通过结果不等于最终提交具备 CI 守护。 |
| GitHub Actions | 当前 PR 版本不包含文档工作流；9792413 上曾触发的成功记录不代表本次提交有 CI 检查。 |

## 未覆盖项

没有应用或应用测试套件，也没有冻结语义集。未运行 Proxy/Agnes/Langfuse 集成、真实模型或 DOI API、取消/截止时间/性能、论文语义验收或正式研究。文本定位、判据摘要、审计缺口及统计规则均是待实现的契约，尚无应用测试证明。未全量检查外链；不声称检查了所有敏感信息。

后续验证记录须关联实际提交，逐项列出环境、命令、真实结果和未覆盖项。不可用临时检查结果或旧提交 CI 冒充当前提交验证。

## 骨架评审修正

| 项目 | 记录 |
| --- | --- |
| 状态 | 在 `codex/project-scaffold` 上处理 PR #4 评审；父提交 `c588193`。本记录与修正在同一提交 |
| 环境 | Linux、Python 3.12.14、Node.js v26.10.0、npm 12.2.0。仓库未配置 CI，结果来自本地检查 |
| 对象 | 接口占位、领域契约、端口说明、锁定文件、README、开发指南和前端类型。没有来源解析、持久化、模型调用或任务执行实现 |

## 实际检查

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q` | 21 passed，1 条 Starlette TestClient 对 httpx 的弃用警告 |
| `backend/.venv/bin/python -m pip check` | No broken requirements found |
| `npm --prefix frontend ci && npm --prefix frontend run build` | 安装锁定依赖后，vue-tsc 与 Vite 构建通过 |
| README 与开发指南的本地链接、`git diff --check` | 本地链接均存在；`git diff --check` 无输出 |

## 未覆盖项

来源解析、持久化、真实模型调用、任务执行和论文语义验收仍未实现。没有在 Windows 上重跑测试；Windows 失败来自评审记录的 `socket.connect` 拦截，本次改为拦截 `create_connection` 与 `getaddrinfo`，并在 Windows 上改用选择器事件循环，但本机没有复现。临时目录为空不能证明没有绝对路径写入。没有性能、取消时限或真实论文验收数据。