# 端到端维度（界面主路径）

`docs/test-plan.md` 把界面主路径放在这里，用 Playwright 覆盖：确认来源 → 同意整次任务的
接收方/数据范围/预算 → 查看 paper agent 的判断与原文位置 → 澄清重提、取消排队/运行中的
任务、显示超时、书目导出预览、删除本地记录。

上游全部换成本机替身，所以这套用例**只判定界面与状态流转**，不产出论文语义结论，也不产出
性能数字。语义真值在 `tests/functional/` 的冻结样本里；单进程调度与时限口径另属性能维度。

## 依赖

依赖放在本目录，**不改** `frontend/package.json`（Issue #26 记录了归属协调）：

```bash
cd tests/e2e
npm ci
npx playwright install chromium      # 或用 npm run browser
```

## 运行

```bash
cd tests/e2e
PAPER_EVIDENCE_E2E_PYTHON=<后端 venv 的 python> npm test
```

`playwright.config.ts` 会自己起四个进程（替身 8765 → 真 API 8000 → 常驻 worker 8001 →
前端 dev server 5173），所以：

- 运行前这四个端口必须是空的；端口写死是因为 `frontend/vite.config.ts` 把 `/api`、`/health`
  固定代理到 8000，前端 dev server 也固定 5173。
- `PAPER_EVIDENCE_E2E_PYTHON` 只在「后端 venv 不在本工作树」时才需要指定（默认找
  `backend/.venv`）。工作树里没有 `frontend/node_modules` 时也要先补上。
- 不需要模型密钥：模型网关也由替身充当，不访问网络。

## 目录

| 路径 | 作用 |
| --- | --- |
| `playwright.config.ts` | 四个 `webServer`、端口、每轮独立的数据目录与输出目录 |
| `support/upstreams.py` | 四类来源端点 + OpenAI 兼容模型网关的本机替身，含 `/_stub/*` 控制端点 |
| `support/runtime.py` | 两个 Python 进程共用的 `Settings`（把五个来源地址指到替身） |
| `support/serve_backend.py` / `support/serve_worker.py` | 真 API 与常驻 worker 的启动入口 |
| `specs/*.spec.ts` | 用例；`specs/helpers.ts` 是共用动作 |

`.run/` 是本轮运行的临时空间（任务库、轨迹、报告），已被 gitignore；每轮用独立目录，
不会覆盖上一轮，也不会被下一轮读到。
