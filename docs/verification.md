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
| 文档链接、示例及契约 | 本轮没有保留可复用的自动检查器。前一临时版本曾运行一次性静态检查及检查器回归，但对应脚本和工作流按用户要求移除；其通过结果不等于该修订具备文档检查。 |
| GitHub Actions | 该修订不包含文档工作流；9792413 上曾触发的成功记录不代表该提交跑过文档检查。仓库现有 CI 为 `backend` 与 `frontend`，不含文档检查。 |

## 未覆盖项

没有应用或应用测试套件，也没有冻结语义集。未运行 Proxy/Agnes/Langfuse 集成、真实模型或 DOI API、取消/截止时间/性能、论文语义验收或正式研究。文本定位、判据摘要、审计缺口及统计规则均是待实现的契约，尚无应用测试证明。未全量检查外链；不声称检查了所有敏感信息。

后续验证记录须关联实际提交，逐项列出环境、命令、真实结果和未覆盖项。不可用临时检查结果或旧提交 CI 冒充当前提交验证。

## 骨架评审修正

| 项目 | 记录 |
| --- | --- |
| 状态 | 在 `codex/project-scaffold` 上处理 PR #4 评审；父提交 `c588193`。本记录随修正提交 `47d15191226d0c394598dec7548433fbc0400bc2` 落地 |
| 环境 | Linux、Python 3.12.14、Node.js v26.10.0、npm 12.2.0。结果来自本地检查。仓库现有 CI：`backend` 执行 pytest，`frontend` 执行前端测试与构建 |
| 对象 | 接口占位、领域契约、端口说明、锁定文件、README、开发指南和前端类型。没有来源解析、持久化、模型调用或任务执行实现 |

## 骨架评审修正：实际检查

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q` | 21 passed，1 条 Starlette TestClient 对 httpx 的弃用警告 |
| `backend/.venv/bin/python -m pip check` | No broken requirements found |
| `npm --prefix frontend ci && npm --prefix frontend run build` | 安装锁定依赖后，vue-tsc 与 Vite 构建通过 |
| README 与开发指南的本地链接、`git diff --check` | 本地链接均存在；`git diff --check` 无输出 |

## 骨架评审修正：未覆盖项

来源解析、持久化、真实模型调用、任务执行和论文语义验收仍未实现。实现方没有在 Windows 上重跑测试；原 Windows 失败来自评审记录的 `socket.connect` 拦截，本次改为拦截 `create_connection` 与 `getaddrinfo`，并在 Windows 上改用选择器事件循环。[评审方复审](https://github.com/wynxing/paper-evidence-agent/pull/4#issuecomment-5950892819)报告在 Windows / Python 3.13 上复现此提交为 21 passed、1 warning；这是第三方记录，不是实现方本机验证，也不代表 editable 安装支持 Python 3.13。临时目录为空不能证明没有绝对路径写入。没有性能、取消时限或真实论文验收数据。

## 最新复审修正（2026-10-02）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `51b2a25929daadf9219fe2bd215dc6bee9e0ba0b`；先提交代码及契约文档，再在独立记录提交中写入本节，避免提交哈希自指 |
| 关联 | PR #4 最新复审 N1–N6；在独立工作树、临时分支 `codex/pr4-review-followup` 修复，普通推送回原分支 `codex/project-scaffold` |
| 环境 | Linux、Python 3.12.14、Node.js v26.10.0、npm 12.2.0；新建 venv 并安装既有锁定依赖。没有新增依赖 |
| 改动 | 保留 HTTP 错误响应头、来源预览 ContractError 映射、创建任务 409 模型、422 脱敏字段信息、TS 对象形状及响应状态双向检查、默认预算/超时工厂和平台说明 |

### 最新复审修正：实际检查

以下命令均从独立工作树的仓库根目录执行，完整测试和构建在对象提交已落地且工作区干净时运行。

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/bin/python -m pip install -r backend/requirements.lock` | 新 venv 安装锁定的运行、测试和构建依赖成功 |
| `backend/.venv/bin/python -m pip install --no-deps --no-build-isolation -e backend` | editable 安装成功 |
| `npm --prefix frontend ci` | 安装 45 个锁定包成功，安装输出报告 0 vulnerabilities；未升级依赖 |
| `backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q` | **54 passed，1 warning**。警告仍为 Starlette TestClient 对 httpx 的弃用提示，未隐藏或新增 httpx2 |
| `backend/.venv/bin/python -m pip check` | No broken requirements found |
| `npm --prefix frontend run build` | vue-tsc 类型检查及 Vite 生产构建通过 |
| 本地 Markdown 文件链接检查（Python 内联脚本，见下方命令） | README、architecture、development、verification 四文件共 41 个本地文件链接存在；不检查锚点及外部 URL |
| `git diff --check`、`git diff --cached --check`、暂存文件范围与凭据模式检查 | 无空白错误；代码提交仅 11 个任务文件，未包含环境、node_modules、dist 或缓存；未匹配私钥、OpenAI/AWS/GitHub 凭据模式。不是全仓敏感信息审计 |

链接检查命令：

```bash
backend/.venv/bin/python - <<'PY'
import re
from pathlib import Path
files = [Path('README.md'), Path('docs/architecture.md'), Path('docs/development.md'), Path('docs/verification.md')]
count = 0
for source in files:
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', source.read_text(encoding='utf-8')):
        path = target.split('#', 1)[0]
        if not path or re.match(r'[a-z]+://', path):
            continue
        assert (source.parent / path).is_file(), (source, target)
        count += 1
print(f'{count} local file links passed')
PY
```

### 最新复审修正：失败与修复过程

初轮完整测试为 **4 failed / 49 passed**：422 脱敏字段路径使用了当前 FastAPI 已移除的 ModelField.type_，导致已声明的字段也被遮成 `<unknown>`。对照安装版本确认应读取 field_info.annotation 后修复；新增公共响应规则检查后，对象提交的完整套件为上述 54 passed。没有削弱字段路径断言。首次提交因环境未配置 Git 作者身份失败，随后仅在提交命令中沿用原 PR 提交的作者身份，没有修改全局或仓库配置。

### 最新复审修正：覆盖与限制

新增检查使用合成请求及测试应用：九种来源预览业务错误保留真实错误码和 HTTP 映射；未定义的错误或其他端点不会被预览映射重分类；405 保留 Allow、自定义头透传、结构化 HTTPException 日志不含原始键值；422 覆盖缺字段、类型错误、非法 JSON、查询字段、数组位置及额外字段脱敏。前后端对象检查覆盖继承、Omit、字段集合、必填性和可空性，包含刻意改变接口的失败用例；响应状态检查覆盖两侧状态增删、错误模型及公共规则移除。七个默认配置值从术语表核对，并验证每次生成独立实例。

业务路由仍为 501，健康检查仍为 200。未实现或验证真实来源请求、任务持久化、模型接入、业务取消/超时执行、性能、论文语义或诊断脱敏能力。对象形状检查不等于完整 TypeScript/OpenAPI 类型等价证明。此新提交未在 Windows 上重跑；上一轮评审方的 21 passed 不能代替本轮 Windows 验证。仓库现有 CI 为 `backend` 与 `frontend`。仍需未参与实现的团队成员独立复审后再考虑合并。

## 后端实现验证记录（2026-10-08）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `7d1c04d24cdfd33ef17347c94f061ac59df8bc1f`；本记录在独立提交中写入，避免提交哈希自指 |
| 关联 | 分支 `feat/backend-implementation`；按 [AGENTS.md](../AGENTS.md) 从更新的 `origin/main` 新建工作树 `.worktrees/backend-impl`，未在主工作区修改 |
| 环境 | Windows / Git Bash、Python 3.12.14、Node.js v22.22.2、npm 10.9.7；新建 venv 安装 `backend/requirements.lock` 与 editable 包；未新增依赖 |
| 对象 | 后端实现：领域摘要与文本契约、SQLite+FTS5 存储、FTS5 检索与 JATS 冻结、来源连接器、模型网关、有界核验状态机、诊断投影、本地轨迹、HTTP 路由与单进程 worker；README 与开发指南同步更新 |

### 后端实现验证记录：实际检查

以下命令均从工作树仓库根目录执行；完整测试与构建在对象提交已落地后运行。

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml -q` | **108 passed，1 warning**。警告仍为 Starlette TestClient 对 httpx 的既有弃用提示，未隐藏 |
| `backend/.venv/Scripts/python.exe -m pip check` | No broken requirements found |
| `npm --prefix frontend ci`、`npm --prefix frontend run build` | 安装锁定依赖成功；vue-tsc 类型检查与 Vite 生产构建通过 |
| `PAPER_EVIDENCE_DATA_DIR=<临时目录> backend/.venv/Scripts/python.exe -m paper_evidence.worker` | 退出码 `0`，输出“本次处理了 0 个任务，队列已空” |
| 本地 Markdown 文件链接检查（README、architecture、development、verification） | 42 个本地文件链接存在；不检查锚点及外部 URL |
| `git diff --cached --check`、暂存文件范围与凭据模式检查 | 无空白错误；代码提交含 37 个任务文件，未包含环境、`node_modules`、`dist` 或缓存；未匹配常见私钥与 token 模式。不是全仓敏感信息审计 |

### 后端实现验证记录：失败与修复过程

实现进行中的一轮为 **4 failed / 104 passed**：两处是实现与契约不一致（DOI 未按大小写不敏感标准化、PMC 记录缺少许可时先于正文语言门槛报错），两处是用例期望写错（负零摘要、引号重复位置）。分别修正 `normalize_doi` 的小写标准化、在来源测试夹具中补上 CC BY 许可声明、并修正用例期望；未削弱任何断言。另修复 `class SqliteStore` 内的 `list` 方法遮蔽内置名导致的注解求值错误（改用 `from __future__ import annotations`）。对象提交最终为本节的 108 passed。

### 后端实现验证记录：覆盖与限制

覆盖：OpenAPI 响应表与架构文档双向一致（不再放宽 `501`）、前端对象形状、领域枚举与默认预算、规范 JSON 摘要与文本/定位契约、FTS5 查询编译与 JATS 确定性、来源内检索与索引故障返回 `RETRIEVAL_FAILED`、任务路由的创建/授权/取消/重试/删除/反馈/诊断脱敏、来源与网关的状态映射（含 `httpx.MockTransport` 桩）、有界工作流的正常/补读/全局修复/预算耗尽/来源阻断/总超时/已受理取消出口。

未覆盖：真实 Crossref、DOI 官方解析服务、PMC ID 转换与 OAI-PMH、OpenAlex 和本机 LiteLLM Proxy 的连通性与契约；Agnes 或任何真实模型调用；LangGraph 编排（当前为等价的显式状态机 `graph/workflow.py`）；Langfuse 导出；Playwright 端到端；论文语义验收与研究评测。单 worker、一次一任务的并发假设未做压力验证。该提交未在 Linux 上重跑。仓库现有 CI 为 `backend` 与 `frontend`。仍需未参与实现的团队成员独立复审后再考虑合并。

## PR #8 复审修正（2026-10-08）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `b0ace2963625b7d584edba766bb91d939a21f1d7`；本记录在独立提交中写入，避免提交哈希自指 |
| 关联 | [PR #8 复审](https://github.com/wynxing/paper-evidence-agent/pull/8#pullrequestreview-5455493360)（`2cf33e6` 上 4 项阻塞、3 项建议同 PR 修、8 项非阻塞建议）；分支 `feat/backend-implementation`，仍在工作树 `.worktrees/backend-impl` |
| 环境 | Windows / Git Bash、Python 3.12.14、Node.js v22.22.2、npm 10.9.7；沿用既有 venv 与锁定依赖，未新增依赖 |
| 对象 | `graph/workflow.py`、`agents/output.py`、`agents/prompts.py`、`api/app.py`、`config.py`、`domain/rules.py`、`domain/records.py`、`models/gateway.py`、`retrieval/`、`sources/`、`storage/sqlite.py`、`worker/runner.py` 及对应测试与开发指南 |

### 复审意见的处置

| 复审意见 | 处置 |
| --- | --- |
| 阻塞 1：确定判断零摘录也会发布 | `_build_decision` 对「支持/部分支持/相矛盾」要求至少一条摘录，否则抛 `QuoteError` 走一次全局修复；`DEFINITIVE_LABELS` 与判据快照同步记录该门槛。「证据不足」仍可无摘录 |
| 阻塞 2：修复输出不可解析时撞 assert | `_repair_action` 解析失败改为抛 `ContractError(MODEL_INVALID_OUTPUT)`；`_verify` 的 `assert` 改为显式 raise；后端已无 `assert`（`python -O` 下不再出现 `None.decision`） |
| 阻塞 3：只给邻居 ID 的 retrieve 必然失败 | `_search` 在 queries 为空时跳过 MATCH 只读邻居；`RetrieveAction` 校验「至少一个非空 queries 或已知邻居 ID」；首次检索为空时要求非空 queries，两类都在派发前走输出校验与修复 |
| 阻塞 4：授权快照可被扩大；诊断接收方用错列表 | 入队前校验 `set(authorized_recipients) ⊆ {primary, *fallback}`，越界 400；全量接收方改为有序元组，使摘要与 `/api/run-config` 一致；诊断导出改由运行配置的观测/诊断接收方授权，未配置或不等时 400 |
| 建议 5：摘录错误的错误码 | `_repair_request` 增加 `exhausted_code`：摘录校验失败且修复额度用尽报 `QUOTE_MISMATCH`，结构/动作修复仍报 `MODEL_INVALID_OUTPUT` |
| 建议 6：上游认证/参数错误被当成无来源 | `convert_to_pmcid`、`crossref.metadata` 和 DOI 解析探测改用 `classify_status()`；只有 200 且无 pmcid 才是 `SOURCE_UNAVAILABLE` |
| 建议 7：`access_url` 指向非冻结版本 | `access_url` 与证据 `source_url` 固定为实际冻结的 PMC 版本 URL；OpenAlex 位置改存本地线索列 `sources.open_locations`，不进入诊断包 |
| 非阻塞：墙钟时间戳 | `claimed_at`/`deadline_at` 改为墙钟 UTC 秒，取消入口的到期判定与 API 读同一时钟 |
| 非阻塞：worker 未传 deadline | `SourceResolver.resolve` 增加可选 deadline，worker 的 `source_identity` 阶段把任务剩余时间传入来源连接器 |
| 非阻塞：证据段落未限定上下文 | `_build_decision` 只接受进入本次判断上下文的段落 ID |
| 非阻塞：邻居读取是空操作 | `read_neighbors` 真正返回 `ordinal±1` 相邻段落，新增 `read_paragraph` 精确读取；提示词与端口说明同步 |
| 非阻塞：`delete` 多次事务 | 删除（含按引用回收来源缓存）合并为单个事务 |
| 非阻塞：失败路径 `params_digest` | `ModelFailure` 携带完整 `ModelCall`，成功与失败路径共用同一 `params_digest` |
| 非阻塞：ElementTree 前提 | 开发指南注明 PMC OAI-PMH 使用标准库 `xml.etree.ElementTree`（expat）及其实体膨胀限制为前提 |

### PR #8 复审修正：实际检查

以下命令均从工作树仓库根目录执行。

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml -q --basetemp=<临时目录>` | **138 passed，1 warning**（净增 30 条用例）。警告仍为 Starlette TestClient 对 httpx 的既有弃用提示，未隐藏 |
| `backend/.venv/Scripts/python.exe -m pip check` | No broken requirements found |
| `npm --prefix frontend run build` | vue-tsc 类型检查与 Vite 生产构建通过（前端未改动） |
| `PAPER_EVIDENCE_DATA_DIR=<临时目录> backend/.venv/Scripts/python.exe -m paper_evidence.worker` | 退出码 `0`，输出“本次处理了 0 个任务，队列已空” |
| `grep -rn "assert " backend/paper_evidence/` | 无匹配；后端不再依赖运行时断言 |
| `backend/.venv/Scripts/python.exe -O -c "..."`（导入 workflow 与 gateway） | 优化模式下导入正常 |

说明：不加 `--basetemp` 时，测试进度到 100% 后本机沙箱的 safe-delete 守卫会拦截 pytest 清理历史临时目录（`SAFE_DELETE_BULK_GUARD_ERROR`），导致汇总行未打印、退出码为 1；进度点共 138 个且无 `F`/`E`。使用独立 `--basetemp` 可得完整汇总，即上表的 138 passed。

### PR #8 复审修正：失败与修复过程

首轮完整测试为 **11 failed / 97 passed**，其中 9 条是测试替身与期望未随接口同步（`FakeResolver.resolve` 新增 deadline 形参、`ModelFailure` 改为携带 `ModelCall`、`access_url` 期望值），2 条是实现缺陷。新增回归用例又暴露一处复审未提到的既有缺陷：`_decide` 与 `_generate_queries` 的修复路径漏传 `repairs_request_id`，一旦输出结构错误就会抛 `TypeError` 并被记成 `FAILED + error_code=null`；已补齐目标请求 ID 并留下用例。另移除 `sources/http.py` 与 `storage/sqlite.py` 中两处同类断言依赖。未削弱任何断言。

### PR #8 复审修正：覆盖与限制

新增覆盖：确定判断零摘录（修复后发布 / 修复后仍失败为 `QUOTE_MISMATCH`）、「证据不足」可无摘录、修复输出不可解析与请求 3 修复不可解析均为 `MODEL_INVALID_OUTPUT`、仅邻居 retrieve 成功且不消耗修复额度、无 queries 无邻居的 retrieve 被修复、首次空检索拒绝仅邻居 retrieve、引用上下文外段落被修复、摘录错误在修复额度用尽时报 `QUOTE_MISMATCH`、失败与成功路径 `params_digest` 一致、接收方越权 400 与收窄 202、诊断导出只认观测接收方、PMC 转换与 Crossref 的 401/403/400/503 映射、`access_url` 归属、邻居读取与精确读取、墙钟截止时间与到期结算、RUNNING 取消结算、删除的引用计数与单事务。

未覆盖（与上一节相同并新增）：真实 Crossref、DOI 官方解析、PMC ID 转换与 OAI-PMH、OpenAlex、本机 LiteLLM Proxy 仍未实测，连接器与网关只用 `httpx.MockTransport`；论文语义验收与研究评测未执行；LangGraph 编排、Langfuse 导出、Playwright 端到端仍未接入；并发与性能未压测。已知限制：任务在 RUNNING 期间被受理取消后，若结果写入恰好落在工作流最后一次取消检查与终态写入之间，该终态仍会按结果提交（存储层的条件写入只保护已提交的终态）；已受理取消与完成结果之间的优先级需在实现取消先行语义时一并处理，本轮未改动该写入条件。该已知限制已由下一节「取消竞态修正（2026-10-09）」关闭。本提交未在 Linux 上重跑。仓库现有 CI 为 `backend` 与 `frontend`。仍需未参与实现的团队成员独立复审后再考虑合并。

## 取消竞态修正（2026-10-09）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `0f786da840ee243d63a4a4bcc0e29351d08d8d95`；本记录在独立提交中写入，避免提交哈希自指 |
| 关联 | [独立复审复现](https://github.com/wynxing/paper-evidence-agent/pull/8#issuecomment-6062135693)（`283819e0`）与 [复审更新](https://github.com/wynxing/paper-evidence-agent/pull/8#pullrequestreview-5458224438)：上轮被定为「已知限制」的取消竞态改判阻塞，`283819e0` 上的 APPROVE 撤回 |
| 环境 | Windows / Git Bash、Python 3.12.14、Node.js v22.22.2、npm 10.9.7；沿用既有 venv 与锁定依赖，未新增依赖 |
| 对象 | `storage/sqlite.py`、`graph/workflow.py`、`worker/runner.py`、`tests/boundary/test_storage_lifecycle.py`、`tests/session/test_workflow.py`、`docs/development.md` |

### 取消竞态修正：缺陷与根因

复审复现：任务经 `claim_next` 进入 `RUNNING` 后受理取消，最终仍落 `COMPLETED` 并带确定判断。根因有两处：

- `SqliteStore.finish()` 的写入条件为 `status IN ('QUEUED', 'RUNNING')`，只保护已提交的终态，不检查 `cancel_requested`；
- `_check_cancel` 只在 `run` / `_main_request` / `_repair_request` / `_search` 调用，`_validate → _build_decision → _complete → _finish` 之间没有检查点，窗口跨过整次最终模型调用。

这与 `docs/prd.md` FR-4（受理取消时显示「正在取消」，本地执行结束后显示「已取消」）和 `docs/test-plan.md`「取消先于完成」不符。

### 处置

| 建议 | 处置 |
| --- | --- |
| `_complete` / `_terminal` 落库前复查 `cancel_accepted` | 已实现：两处在写入前复查，已受理则走 `_cancel` |
| `finish()` 不得让非 `CANCELLED` 终态覆盖 `cancel_requested = 1` 的 RUNNING 任务 | 已实现：SQL 条件加 `(? = 'CANCELLED' OR cancel_requested = 0)`，在同一事务内判定；`_finish` 返回写入是否成功，被拒时 `_after_refused_write` 收敛为取消优先，否则读取已提交终态 |
| 补回归：必须经 `claim_next` 进入 RUNNING 后再 `request_cancel`，断言终态 `CANCELLED` | 已补：storage 与 session 两处；session 用例用网关钩子在最终 decision 响应返回时受理取消，复现复审路径 |

两条建议都做了：流程内复查缩小窗口，存储层条件写入把窗口原子关闭。取消现在同时优先于「完成」与「失败」。

### 取消竞态修正：实际检查

以下命令均从工作树仓库根目录执行。

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml -q --basetemp=<临时目录>` | **142 passed，1 warning**（净增 4 条用例）。警告仍为 Starlette TestClient 对 httpx 的既有弃用提示，未隐藏 |
| `git stash push -- backend/paper_evidence/storage/sqlite.py backend/paper_evidence/graph/workflow.py` 后重跑 4 条新用例 | **3 failed / 1 passed**：取消优先级用例全部失败，护栏用例（无取消时普通完成照常写入）仍通过；随后 `git stash pop` 恢复。确认回归用例可复现该缺陷，不是恒真断言 |
| `backend/.venv/Scripts/python.exe -m pip check` | No broken requirements found |
| `npm --prefix frontend run build` | vue-tsc 类型检查与 Vite 生产构建通过（前端未改动） |
| `PAPER_EVIDENCE_DATA_DIR=<临时目录> backend/.venv/Scripts/python.exe -m paper_evidence.worker` | 退出码 `0`，输出“本次处理了 0 个任务，队列已空” |

### 取消竞态修正：覆盖与限制

新增覆盖：RUNNING + 已受理取消时 `COMPLETED` 与 `FAILED` 写入均被拒且状态保持 `RUNNING`、随后 `CANCELLED` 落库；无取消时普通完成仍写入（守卫不误伤）；取消在最终 decision 响应返回时受理 → 终态 `CANCELLED` 且 `label`/`decision` 为 `null`；取消先于上游失败受理 → 终态 `CANCELLED` 而非 `FAILED`。

未覆盖（沿用上节）：真实 Crossref、DOI 官方解析、PMC ID 转换与 OAI-PMH、OpenAlex、本机 LiteLLM Proxy 仍未实测，连接器与网关只用 `httpx.MockTransport`；论文语义验收与研究评测未执行；LangGraph 编排、Langfuse 导出、Playwright 端到端仍未接入；并发与性能未压测，单 worker、一次一任务的假设未做压力验证。本提交未在 Linux 上重跑。仓库现有 CI 为 `backend` 与 `frontend`。仍需未参与实现的团队成员独立复审后再考虑合并。

## 前端工作台编排层（2026-10-10）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `af780eb06601ade2ef86dea4ac4ab32e5063a251`；本节在其后的独立提交中写入，避免提交哈希自指 |
| 关联 | PR #5 评审延后的 N4（`useWorkbench` 可注入并补编排测试）与 N5（本记录）；CI 的 `frontend` 作业增加 `npm --prefix frontend test`，作业名仍为 `backend` 与 `frontend` |
| 环境 | Linux、Node.js v22.14.0、npm 10.9.7。命令从仓库根目录执行。未新增依赖，未改锁定文件、后端或公共契约 |
| 对象 | `frontend/src/state/workbench.ts`、`frontend/tests/workbench-orchestration.test.mjs`、`.github/workflows/ci.yml`、README 持续集成两句 |

### 前端工作台编排层：实际检查

`npm ci` 在改代码之前执行，锁定文件与对象提交相同。测试与构建在对象提交落地且工作区干净时执行。差异检查比较的是该提交与 main。

| 检查 | 结果 |
| --- | --- |
| `npm --prefix frontend ci` | 安装 45 个锁定包。安装输出报告 1 个 high severity advisory。未升级依赖 |
| `npm --prefix frontend test` | **32 passed，0 failed**（1 suite）。其中编排层 11 条，原 `frontend/tests/workbench.test.mjs` 21 条。Node 打印 Type Stripping 实验特性警告，未隐藏 |
| `npm --prefix frontend run build` | `vue-tsc --noEmit` 通过，Vite 生产构建通过 |
| `git diff --check origin/main...HEAD` | 无输出，退出码 0。范围是对象提交相对 main，不含本节 |

### 前端工作台编排层：覆盖与限制

编排测试在 Node 内置测试运行器里挂载 `useWorkbench`，注入替身客户端、短间隔的真实轮询器或可控轮询器，以及 hash / 可见性替身。覆盖：提交（含 DOI 规范化、进行中的第二次提交不重发）、轮询推进到终态后停止、网络错误与 503 后续轮询、契约不一致 / 404 / 409 停止轮询、导航后的迟到读取不覆盖当前任务、重试走 `retryCheck` 且新历史行保留 DOI、取消成功后停止轮询、取消失败后续轮询、409 后刷新配置、501 保留草稿且不进入模拟模式、隐藏页面不启动轮询、畸形 hash 提示、注入客户端优先于 demo 模式、未注入时 demo 模式仍用内存客户端、语义导出缺少同意标记时不发请求。

未覆盖：未运行 pytest；未在浏览器中操作工作台；未连接真实后端、文献来源或模型。替身挂载不是 Playwright 端到端。本节不把尚未看到的 CI 结果写成通过。

## 前后端接口缺口（2026-10-11）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `aca988c9423a934e0691e28ed75ed48b9174934f`；本节在其后的独立提交中写入，避免提交哈希自指 |
| 关联 | 前后端接口差异清单（对应 Issue #7）中的 #1、#2、#3、#4、#5、#6、#8、#11；一次契约变更，前后端同批改完 |
| 环境 | Windows、Python 3.12.14、Node.js v22.22.2、npm 10.9.7。后端依赖装在新临时 venv 中，命令从工作树仓库根目录执行。未新增依赖，未改 `pyproject.toml` 依赖列表与锁定文件 |
| 对象 | `backend/paper_evidence/` 下的 `domain/contracts.py`、`domain/text.py`、`storage/sqlite.py`、`sources/service.py`、`config.py`、`api/app.py`、`worker/__main__.py`、`worker/runner.py`；`frontend/src/`；两处契约文档；相关测试 |

### 前后端接口缺口：实际检查

测试与构建在对象提交落地、工作区干净时执行。

| 检查 | 结果 |
| --- | --- |
| `python -m pytest -c pyproject.toml -q --basetemp=<临时目录>` | **158 passed，1 warning**。警告仍为 Starlette TestClient 对 httpx 的既有弃用提示，未隐藏 |
| `npm test`（`frontend/`） | **42 passed，0 failed**（1 suite），此前为 21 条 |
| `npm run build`（`frontend/`） | `vue-tsc --noEmit` 通过，Vite 生产构建通过（29 modules） |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | 无输出，退出码 0 |
| 真实进程探针：`PAPER_EVIDENCE_DATA_DIR=<临时目录> python -m paper_evidence.worker` | 退出码 `0`，stderr 为「worker 本次处理了 0 个任务，队列已空。」，临时目录内生成 `paper-evidence.sqlite3` |
| 真实进程探针：同上加 `--loop --interval 0.05`，等待 4 秒后查进程状态 | 进程仍在运行（队列为空也不退出），确认常驻语义；随后以 `CTRL_BREAK_EVENT` 结束 |

关于中断的实测细节：用 `CTRL_BREAK_EVENT` 结束时进程退出码为 `3221225786`（`0xC000013A`，`STATUS_CONTROL_C_EXIT`），stderr 为空，即 Python 层的中断分支没有机会执行。控制台控制事件如何到达进程因平台与终端而异，因此该路径改由 `tests/boundary/test_domain_contract.py` 的入口层用例固定：`--loop` 走到 `drain_forever`、中断按正常停止处理、退出码 `0`、打印「worker 收到中断，已停止。」。真实信号下的可观测行为在本机 Windows 终端上仍未确认。

### 前后端接口缺口：覆盖

- 契约双向比对：`tests/boundary/test_frontend_shapes.py` 把 `contracts.ts` 与 OpenAPI 逐字段比对（字段名、必填性、可空性、继承与 `Omit`），`tests/tools/test_api_contract.py` 把架构文档的响应状态表与 OpenAPI 双向比对。二者在本轮随契约扩展一起通过，因此新字段的前后端一致是被断言过的，不是只看代码。这 6 条用例在本次之前的工作树里因未安装 Node 与前端依赖而未实际执行。
- 存储：历史行带摘要与创建时间、倒序、筛选；详情返回原句、书目与三个时刻；排队期取消会写 `finished_at`；书目索引保留作者与年份；旧行缺 `authors`/`year` 时按空值读出；用构造的旧版 schema 数据库打开后补齐列且保留原有行。
- 接口：历史与详情返回新字段、按 `status` 筛选；诊断导出对空字符串与全空白收件人返回 `400`，对带首尾空格的已授权收件人按归一化值返回 `200`；配置读取归一化 `"A, B"` 与全空白值。
- 前端：演示数据满足新契约；历史倒序与摘要；详情计时助手在缺失或时间倒挂时返回未知而非估算；未缓存上下文时由任务记录恢复原句，从而「修改原句」「拆分论断」可用，且任务未记录原句时仍拒绝；重试草稿仍不填原句。

### 前后端接口缺口：未覆盖

- 没有真实上游调用。Crossref、DOI 官方解析、PMC ID 转换与 OAI-PMH、OpenAlex、本机 LiteLLM Proxy 仍未实测，连接器与网关只用 `httpx.MockTransport`。
- 没有端到端联调。前端轮询 + 常驻 worker + 真实取回全文的完整链路未跑通；“任务从 `QUEUED` 进入 `RUNNING` 并被前端看到”只有单元与编排测试支持，没有跨进程实测。
- worker 重启后遗留 `RUNNING` 的重试路径（清单 #7）未做跨进程联调，只有存储层用例。
- 清单 #10（是否在授权页展示实际模型与部署）仍待产品确认，本轮未改；#12（证据邻段只读接口）与 #13（前端 501 死代码清理）本轮未做。
- 论文语义验收、正式研究评测、LangGraph 编排、Langfuse 导出、Playwright 端到端仍未接入；取消、截止时间与并发未压测，单 worker、一次一任务的假设未做压力验证。
- 迁移只在构造的一版旧 schema 上验证，未覆盖真实使用过的数据库；`paragraphs`、`check_sources` 等表本轮未新增列，其迁移分支未被触发。
- 本提交未在 Linux 或其他 Python 版本上重跑，只在 Windows / Python 3.12.14 上验证；真实进程探针的结论也只属于该平台。仓库现有 CI 为 `backend` 与 `frontend`。

## PMC OAI 取回链路修复（2026-10-11）

| 项目 | 记录 |
| --- | --- |
| 关联 | 独立端到端复核发现：真实网络中 `fetch` 阶段恒定失败于 `UPSTREAM_INVALID_REQUEST`。属新增发现，非既有清单项 |
| 环境 | Windows / Git Bash、Python 3.12.13、Node.js v22.22.2、npm 10.9.7。命令从仓库根目录执行。未新增依赖 |

### PMC OAI 取回链路修复：缺陷与根因

三项叠加，全部在 PMC 全文取回链路上，mock 测试无法暴露：

1. `config.py` 的默认 `pmc_oai_url` 仍指向 `https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi`，该地址现返回 **301**，重定向到 `https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`。
2. `pmc.py` 的 `fetch_record` 请求 `metadataPrefix=pmc`，但该前缀对多数记录返回 **400 `cannotDisseminateFormat`**；`ListMetadataFormats` 返回可用值为 `oai_dc`、`pmc`、`pmc_fm`，其中**只有 `pmc_fm` 返回含 `<article>` 的完整 JATS 正文**。
   > ⚠️ **该结论已于 2026-10-12 被实测推翻（Issue #28）**：`pmc_fm` 返回的 `<article>` **不含 `<body>`**，只有题录+摘要；`pmc` 才返回正文（OA 子集记录，3/3 样例）。详见「PMC 全文取回：metadataPrefix 修正」一节。此处保留原文以说明当时的判断依据。
3. `pmc.py` 调用 `Fetcher.get` 时未传 `follow_redirects=True`；`http.py` 默认 `False`，且 301 小于 400 会被 `Fetcher` 原样返回，随后在 `fetch_record` 的 `status_code != 200` 分支被记为 `UPSTREAM_INVALID_REQUEST`。

### PMC OAI 取回链路修复：修复

- `config.py`：默认端点改为 `https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`。
- `pmc.py`：`metadataPrefix` 改为 `pmc_fm`（**已于 2026-10-12 订正为先 `pmc`、仅在 `cannotDisseminateFormat` 时回落 `pmc_fm`，详见「PMC 全文取回：metadataPrefix 修正」一节**）；`fetch_record` 的请求显式传 `follow_redirects=True`。

### PMC OAI 取回链路修复：实际检查

测试在改动落地、工作区干净时执行。

| 检查 | 结果 |
| --- | --- |
| `python -m pytest -c pyproject.toml -q --basetemp=<临时目录>` | **162 passed，1 warning**（新增 4 条契约用例；警告仍为既有 Starlette/httpx 弃用提示） |
| `npm test`（`frontend/`） | 42 passed，0 failed |
| 真实端到端：新建任务后运行 worker | 修复前 `FAILED / stage=fetch / UPSTREAM_INVALID_REQUEST`；修复后 **`fetch` 阶段 `success`**，`query_generation` 才失败于 `UPSTREAM_UNAVAILABLE`（本机 LiteLLM Proxy 未运行），`main_requests_used=1` |
| 反向验证：将三处改动还原为修复前状态后重跑新增用例 | **3 failed**（端点、前缀、重定向各一条），确认新用例非恒真断言 |
| 许可门控交叉验证：对无 license 标签的 10.1038/nature12373 | `fetch` 阶段返回 `LICENSE_UNKNOWN`，属预期门控而非链路故障 |
| `git diff --check` | 无输出，退出码 0 |

修复后实测执行轨迹（DOI `10.1371/journal.pmed.0020124`，CC BY 4.0）：

```
source_identity      success
fetch                success    ← 此前恒为 error
query_generation     error      UPSTREAM_UNAVAILABLE（Proxy 未启动）
```

### PMC OAI 取回链路修复：未覆盖

- 未验证真实模型调用：本机 LiteLLM Proxy（`127.0.0.1:4000`）未运行，`query_generation` 及之后的判断、证据校验阶段仍未在真实上游下跑通。
- 端到端只到 `fetch` 为止，仍是单进程内直接调用 `drain`，未使用 PR #15 的 `--loop` 常驻模式做跨进程联调。
- 新契约用例固定的是本客户端发出的请求形状，不校验 PMC 服务端当前真实返回；上游再次变更端点或格式时仍需人工复核。
- 论文语义验收、正式研究评测、Playwright 端到端、并发与性能仍未覆盖。
- 本次仅在 Windows / Python 3.12.13 上验证。仓库现有 CI 为 `backend` 与 `frontend`。

## 模型传输切到进程内 LiteLLM SDK（2026-10-11）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `4fde800b6ca529d0660aa269eaf13f74bc54bd0b`；本节在其后的独立提交中写入，避免提交哈希自指 |
| 关联 | Issue #18：模型请求原先必须经过本机 LiteLLM Proxy，现改为默认在进程内用 LiteLLM 库调用，Proxy 保留为可选传输 |
| 环境 | Windows、Python 3.12.14、Node.js v22.22.2、npm 10.9.7。后端依赖装在新建的空 venv 中，只按 `backend/requirements.lock` 安装，再以 `--no-deps --no-build-isolation` 装本地 editable 包，与仓库 CI 的安装顺序一致 |
| 对象 | `backend/paper_evidence/models/` 新增 `sdk.py`、`recording.py`，改写 `gateway.py`、`ports.py`；`config.py`、`api/deps.py`；`backend/pyproject.toml`、`backend/requirements.lock`；`tests/tools/test_sdk_gateway.py`（新增）、`tests/tools/test_checks_api.py`、`tests/boundary/test_domain_contract.py`；README 与七份文档 |

新增依赖 `litellm==1.105.0` 已获用户明确授权（此前 `AGENTS.md` 要求不擅自加依赖）。

### 模型传输切到进程内 LiteLLM SDK：实际检查

| 检查 | 结果 |
| --- | --- |
| 空 venv 装 `backend/requirements.lock` | 67 个包全部装上，含 `litellm-1.105.0`、`openai-2.54.0`、`h2-4.4.1`；无版本冲突 |
| `python -m pip check` | No broken requirements found |
| `python -m pytest -c backend/pyproject.toml -q` | **197 passed，2 warnings**。两条警告是 Starlette TestClient 对 httpx 的既有弃用提示与 litellm 内部 pydantic TypedDict 提示，均未隐藏。上一条记录的 158 passed 加上本次与上轮新增用例 |
| `npm --prefix frontend test` | **42 passed，0 failed**（1 suite） |
| `npm --prefix frontend run build` | `vue-tsc --noEmit` 通过，Vite 生产构建通过（29 modules） |
| `git diff --check` | 无输出，退出码 0 |
| 真实进程探针：遍历 `litellm.exceptions` 命名空间 | 31 个异常类，未映射 **0** 个 |
| 真实进程探针：上游端口未监听 | `UPSTREAM_UNAVAILABLE`，两次尝试（序号 1、2，第二次 `recovery_kind=retry`），耗时 5.11 秒（含恢复等待） |
| 真实进程探针：不配置密钥与上游地址 | `UPSTREAM_UNAVAILABLE`，两次尝试，0.02 秒内返回（未建立连接） |
| 真实进程探针：deadline 已过期 | `TASK_TIMEOUT`，不产生尝试记录 |
| 真实进程探针：`import litellm` 的价目表抓取 | 不设 `LITELLM_LOCAL_MODEL_COST_MAP` 时每次导入报告 1–2 次抓取尝试（litellm 自身上限 3 次）后回落本地备份，设了之后 0 次 |
| CI（对象提交 `bee9e98`，run 38134749566） | `backend` 与 `frontend` 两个检查均 success。`backend` 在 Linux / Python 3.12 上运行 `pytest -c backend/pyproject.toml -q`，结果为 **197 passed，2 warnings**，与本机一致；这也说明 Retry-After 用例的宽松阈值在 Linux 上同样成立 |

探针查出一处真实缺陷，随本提交修掉：litellm 的 `BadGatewayError`、`InvalidRequestError`、`APIResponseValidationError` 直接继承 `openai` 的基类而非 litellm 的同名类，原来的映射表只列 litellm 同名类、兜底项也取自 `litellm.APIError`，这些类因此漏出未映射。修前「上游端口未监听」会以 `error_code=null`（worker 的未分类失败分支）结束，修后为上表的 `UPSTREAM_UNAVAILABLE`。

### 模型传输切到进程内 LiteLLM SDK：覆盖

- 错误映射：十类 litellm 异常到错误码的映射，并单独固定 `Timeout` 不因继承 `APIConnectionError` 而被读成连接失败。穷尽性用例遍历 `litellm.exceptions` 命名空间，要求每个异常类要么被映射、要么在 `NOT_UPSTREAM_FAILURES` 里显式列出，因此 litellm 升版新增异常类会直接失败，而不是静默漏成 `error_code=null`。
- 恢复：可恢复错误消耗一次恢复额度并记 `recovery_kind=retry`；不可恢复错误不重试；`attempts_per_request=1` 时不重试；Retry-After 被等待；Retry-After 超过任务剩余时间时不消耗预算直接失败；任务余量不足时按 `TASK_TIMEOUT` 结束。
- 记账：成功与失败共用同一个 `params_digest`（不是 request id）；每次尝试序号从 1 起；`usage` 与调用标识缺失时为 `null` 而不是 0。
- 线上载荷：发给 SDK 的是配置的 `openai/agnes-2.5-flash` 而不是别名 `paper-default`；`num_retries` 为 0；未配置 `api_base`/`api_key` 时不发送这两个参数。
- 传输选择：默认 `sdk`；未知取值回落默认；端点类别（`provider_default`/`configured_endpoint`/`local_gateway`）与传输方式进入冻结快照并影响 `config_digest`；`api/deps.py` 按配置构造对应实现。
- SDK 入口本身：两条用例经真实 `litellm.acompletion` 加 `mock_response` 走通，证明真实 `ModelResponse` 里确实取得到调用标识与 usage，真实失败也落到同一张映射表。`mock_response` 在派发前返回，不访问网络。
- 依赖闭包：闭包校验覆盖了新增依赖；`_distribution_name` 现能处理 setuptools 旧式 `name (<1,>=x)` 元数据（botocore 仍是这种写法，此前会让 boto 一整支不被遍历），extra 归属修正为依赖自身，litellm 的 `httpx[http2]` 因此被正确遍历。

### 模型传输切到进程内 LiteLLM SDK：未覆盖

- 没有真实模型调用。Agnes 或任何供应商的端点、鉴权与真实响应形状未实测；本机无网络出口，真实入口验证止于 `mock_response` 与「连不上」两类路径。因此「SDK 形态能拿到真实模型版本」未验证，`verified_model_version` 仍只能是 null。
- Proxy 形态未做真实连通性验证，仍只用 `httpx.MockTransport` 的状态映射用例；`PAPER_EVIDENCE_MODEL_TRANSPORT=gateway` 与真实 LiteLLM Proxy 的联调未做。
- 跨部署回退未实现。规范里「日常模式恢复到已授权备用部署」没有对应代码，配置里也没有备用部署，两种形态都只重试原部署。这是本轮明确不做的范围，已写入 D6 与 decisions.md，不是遗漏。
- Proxy 形态下调用账的缺口未解决：Proxy 内部的重试在本进程不可见，`attempts` 只记派发出去的那一次；SDK 形态下两次都可见。两种形态的诊断保真度因此不同，已写入 D6 后果。
- 端到端联调未做：前端轮询 + 常驻 worker + 真实模型调用的整条链路未跑通。
- Linux 只由 CI 覆盖测试与构建（见上表），没有在 Linux 上单独跑真实进程探针；探针结论仍只属于 Windows / Python 3.12.14。CI 同样没有网络出口，因此它也不覆盖真实模型连通性。
- 未测并发与性能，单 worker、一次一任务的假设未做压力验证；论文语义验收、LangGraph 编排、Langfuse 导出与 Playwright 端到端仍未接入。
- `httpx` 从 dev extra 提到运行时是顺带修的打包缺口，未在「只装 `dependencies`、不装 `requirements.lock`」的路径上单独验证。

### 已知限制

Windows 上 `tests/conftest.py` 选用 selector 事件循环，实测 `asyncio.sleep(0.08)` 会在约 0.078 秒返回。因此 Retry-After 用例断言的是适配层向 `asyncio.sleep` 请求的时长（精确相等），墙上时钟只做宽松校验。把该用例写回「墙上时钟 ≥ 请求时长」会在本平台失败，与实现正确与否无关。

关闭远程价目表下载的收益只有「不再发这次请求」这一条：同一台机器上设与不设的导入耗时都在 4.0–4.2 秒，差异落在噪声里，耗时由 LiteLLM 自身的导入图决定。D6 与开发指南按这个结论表述，没有写成功率提升。

## 功能准确性语义验收（2026-10-12）

| 项目 | 记录 |
| --- | --- |
| 关联 | 测试方案「功能准确性」维度：`tests/functional/` 冻结样本与人工核对标签 |
| 环境 | Windows、Python 3.12.13，`backend/.venv` 由 uv 创建，依赖按 `backend/requirements.lock` 安装 |
| 对象 | `tests/functional/conftest.py`（补完）、`tests/functional/test_semantic_acceptance.py`（新增）、`tests/functional/samples/`（7 份样本） |

该目录此前已有 `conftest.py` 与一份样本，但没有测试文件，且该样本无法被现有解析器接受。本次把它做通，并补足测试方案要求的标签与语义维度覆盖。

### 补完的三处缺陷（接手时实测确认，非推测）

| 缺陷 | 现象 | 处理 |
| --- | --- | --- |
| 样本的 evidence 用 `paragraph`（段号），解析器要求 `paragraph_id`（字符串）且 `extra=forbid` | 照搬样本 transcript 得到 `OutputError: 动作字段不合法` | 保留样本可读的段号写法，在 `ScriptedGateway` 增加 `_resolve`：按冻结 JATS 的文档顺序把 1-based 段号换成真实 `paragraph_id`；越界抛 `SampleReferenceError` 而非静默丢弃摘录 |
| `_load` 读顶层 `payload["doi"]`，样本把 DOI 放在 `source` 块内 | `KeyError: 'doi'` | 改读 `payload["source"]["doi"]`，与 `pmcid`/`version`/`license` 同处一块 |
| `_load` 读 `checks`，样本写作 `expected_checks` | `FrozenCase` 该字段恒为空 | 统一为 `expected_checks`，并注明它是人工可读的验收说明，机器断言以测试模块为准 |

### 验收集覆盖

| 标签 | 样本 | 语义维度 |
| --- | --- | --- |
| 支持 | `support_object_scope` | 对象与条件一致 |
| 部分支持 | `partial_population_scope` | 条件/对象范围被扩大（成人 → 所有年龄组） |
| 部分支持 | `partial_quantity` | 数量不符（20% → 约 50%） |
| 相矛盾 | `contradicted_negation` | 否定方向被翻转 |
| 相矛盾 | `contradicted_object` | 对象被替换（Drug A → Drug B） |
| 相矛盾 | `contradicted_causality` | 因果关系被主张（原文指出下降早于治疗引入） |
| 证据不足 | `insufficient_unrelated` | 检索到内容但均不支持论断 |

### 功能准确性语义验收：实际检查

| 检查 | 结果 |
| --- | --- |
| `pytest ../tests/functional -q` | **19 passed** |
| `pytest -q`（全量，取 `backend/pyproject.toml` 的 `testpaths`） | **220 passed，2 warnings**（201 既有 + 19 新增），无回归 |
| 运行时隔离：`grep -rn "\bsamples\b\|\bfunctional\b\|tests\." backend/paper_evidence/` | **0 命中**，冻结样本与预期不被运行时导入（测试方案「功能准确性」首条） |
| 确定性判定：摘录不在冻结段落时 | `FAILED` / `QUOTE_MISMATCH` / `label=None`，不发布确定判断。同一错误摘录连续给出两次（含一次修复请求）仍拒判 |
| 负向控制：换成语义明确错误的标签 | 验收器检出（`acceptance_failures` 非空） |
| 负向控制：摘录不在被引段落 | 验收器检出 |
| 负向控制：确定判断不带摘录 | 验收器检出 |
| 负向控制：正确对照 | 真实结果通过，验收器不会永远拒判 |
| 可判定覆盖 | 7 份样本的发布标签覆盖 支持/部分支持/相矛盾，未全部以「证据不足」通过 |

正向断言与负向控制共用同一个 `acceptance_failures`，因此控制不通过时不得用该验收器发布语义成绩（测试方案「验收器负向控制」）。

### 功能准确性语义验收：未覆盖

- 样本的 JATS 是**人工构造的最小可解析快照**，不是真实论文原文；`claim_kind` 均为 `constructed` 并附 `claim_note`，不冒充自然引文。测试方案要求的「小规模真实 PMC 来源集」尚未建立。
- 标签由单人整理，尚无第二人复核（测试方案「标注」要求一人整理、另一人复核）。分歧解决前不计为确定真值。
- 上游模型仍由 `ScriptedGateway` 回放，未调用真实模型；本维度检验的是判定链路的确定性与证据门槛，不是模型本身的语义能力。
- 首版 7 例为构造样本，不声称标签稳定，也不给出总体准确率；摘录定位有效率等报告口径尚未产出。

## 对抗与安全维度（2026-10-12）

| 项目 | 记录 |
| --- | --- |
| 关联 | 测试方案「对抗与安全」维度：`tests/adversarial/`。被测模块 `graph/` 对不可信输入的处理与 `sources/` 的端点限制 |
| 环境 | Windows、Python 3.12.13，`backend/.venv` 由 uv 创建，依赖按 `backend/requirements.lock` 安装 |
| 对象 | `tests/adversarial/conftest.py`、`test_untrusted_input.py`、`test_leakage.py`、`test_export_boundary.py`、`test_observability.py`（均为新增） |

### 对抗与安全维度：实际检查

| 检查 | 结果 |
| --- | --- |
| `pytest ../tests/adversarial -q` | **19 passed** |
| `pytest -q`（全量） | **239 passed，2 warnings**（220 既有 + 19 新增），无回归 |
| 注入指令进入判定 prompt 时被标为不可信数据 | prompt 含该文本，且含 `UNTRUSTED_NOTICE`；任务进入 `COMPLETED` 并按模型输出发布标签 |
| 注入指令不影响任务目标与来源绑定 | 提交原句与 `source.doi` 均未被改写；查询生成 prompt 不含正文中的注入文本（该阶段尚未取回正文） |
| 模型不能为未进入上下文的段落作证 | 引用不存在的段落 → `FAILED` / `QUOTE_MISMATCH` / `label=None` |
| 书目不可由模型生成 | 模型输出带 `title` 字段 → `FAILED` / `MODEL_INVALID_OUTPUT`；`source.title` 仍来自冻结原文，伪造值不出现在结果中 |
| 输入中的 URL 不能移动请求 | 恶意 DOI（`http://evil.example/...`、协议相对、路径穿越）下，Crossref 与 DOI resolver 的每个请求 URL 仍在配置的官方前缀内 |
| redacted 包不含敏感标记 | 原句、段落文本、查询三个唯一标记均不出现在包内 |
| 理由与限制字段不能绕过脱敏 | `decision.rationale` 与 `decision.limitations` 均为 `<redacted>` |
| 失败路径同样脱敏 | 拒判（无已发布判断）的 redacted 包同样不含任何标记 |
| 对照：consented 保留原句 | 已授权导出含原句标记，确认遮罩不是无差别丢弃 |
| redacted 保留公开书目 | DOI、PMCID、题名、版本哈希与候选章节均保留，同时论断仍为 `<redacted>` |
| 两种视图结构一致 | schema、case_id、source、status 相同，仅受授权约束的文本不同 |
| 观测默认关闭 | 未设置时 `langfuse_enabled=False`；`""`/`0`/`false`/`no`/`off` 均不启用，仅 `1`/`true`/`yes` 启用 |
| 观测接收方配置缺失或全空白 | 均为 `None`，不产生接收方 |
| 启用观测不改变核验 | 任务仍 `COMPLETED`；模型请求数仍为 2（查询生成 + 判断），不增加业务重试 |

### 对抗与安全维度：未覆盖

- **Langfuse 导出尚未实现**：`tracing/` 只有本地 SQLite 记录器（`LocalTraceRecorder`），没有出站导出路径。因此测试方案中「启用后的故障不改变核验状态、脱敏回调不得带出原句或响应」没有可测对象，本节只覆盖「启用不改变核验结果」与「默认关闭」。**「默认关闭时零网络导出」在本实现下是通过"没有导出代码"而非"导出被关闭"满足的**，实现时必须重新验证。
- **`Fetcher` 没有端点白名单**：`sources/http.py` 的 `get()` 接受任意 URL，端点固定靠调用方约定（各 connector 用构造时传入的配置前缀）。本节从调用方一侧验证了前缀不被输入改变，但没有覆盖"未来新增 connector 是否遵守约定"。
- 未做提示注入的**变形覆盖**（编码绕过、多语言、工具返回值注入等），仅覆盖明文指令一种形态。
- 未测真实模型下的注入抵抗：上游仍由脚本化 gateway 回放，模型对不可信文本的实际服从度未被检验。
- 未覆盖密钥泄漏面：本节未注入凭据标记扫描进程环境、异常与日志，因为当前无密钥可用。

## 端到端联调后端缺口（2026-10-12）

| 项目 | 记录 |
| --- | --- |
| 关联 | Issue #20「依赖后端 @Ziyiqian123」四项，与 Issue #7「待办 → 后端」同批，内含 #16 第 1、2 条 |
| 环境 | Windows、Python 3.12.14（pytest 9.1.1）；Node v22.22.2、`node --test`、`vue-tsc` 3.3.11 + `vite` 8.3.1 |
| 对象 | 后端 `domain/contracts.py`、`storage/sqlite.py`、`api/app.py`、`worker/runner.py`；前端 `src/api/contracts.ts`；文档 `architecture.md`、`development.md`、`README.md`；测试 `tests/tools/test_checks_api.py`、`tests/boundary/test_storage_lifecycle.py`、`tests/boundary/test_domain_contract.py` |
| 对象提交 | 首版 `ca593ca468e8526c2303b2a1c9215f00f43a900b`；评审修正 `3a53dc37b3c2dc6446a46ce793d9816466c108bb`（本记录随后单独提交，避免哈希自指） |

### 四项待办与实现

| 待办 | 实现 |
| --- | --- |
| 证据邻段上下文读取接口 | 新增 `GET /api/checks/{id}/evidence-context` → `EvidenceContext`。锚点为「进入模型上下文的候选段落」与「最终判断引用的段落」，各自经 source-scoped 的 `read_neighbors` 按 `ordinal±1` 展开，按段落序号升序返回；每段带 `entered_context` / `cited` 两个来源标志与自己的 `ordinal`（冻结来源内的正文序号，从 1 起，与展开邻段用的 `ordinal±1` 是同一个值） |
| 原始输入读取接口 | 新增 `GET /api/checks/{id}/input` → `CheckInput`，返回提交时原文以及该任务冻结的 `config_digest` 与 `authorized_recipients`。这是一条**按任务**的直接读取、不依赖历史列表是否已加载；`CheckSummary` 也带 `doi`，故它**不是**取得提交 DOI 的唯一路径（评审修正，见下） |
| #16 第 1 条（worker 遇异常退出） | `run_once` 把工厂构造移入 `try`；`drain_forever` 捕获循环级异常后继续 |
| #16 第 2 条（时间戳一致） | `updated_at` / `finished_at` 由同一处 `_now()` 复用 |
| 最简模型密钥配置说明 | `development.md` / `README.md` 写明最小集与失败行为 |

### 端到端联调后端缺口：实际检查

| 检查 | 结果 |
| --- | --- |
| `pytest ../tests -q`（全量） | **248 passed，3 warnings**，无回归 |
| `pytest ../tests/tools/test_checks_api.py -q` | **30 passed** |
| `pytest ../tests/boundary/test_storage_lifecycle.py ../tests/boundary/test_domain_contract.py -q` | **31 passed** |
| `pytest ../tests/tools/test_api_contract.py ../tests/boundary/test_frontend_shapes.py -q` | **16 passed**（OpenAPI / 架构文档 / 前端契约三方一致） |
| 前端 `node --experimental-strip-types --test tests/*.test.mjs` | **41 passed** |
| 前端 `npm run build`（`vue-tsc --noEmit` + `vite build`） | 通过，29 modules transformed |
| 原始输入逐字返回 | 提交 `"  The intervention reduced mortality.  "`（前后带空白）→ 接口原样返回，不折叠空白、不截断 |
| 详情视图的 DOI 空窗 | 同一时刻 `GET /api/checks/{id}` 的 `source` 为 `null`，详情视图本身在该阶段没有 DOI，`GET .../input` 仍返回提交 DOI；但历史行的 `CheckSummary.doi` 同期也有值，故这是**详情视图**的空窗，不是全局缺口 |
| 重试链保留 | 由 `previous_id` 指向的原任务被取消后，重试任务仍返回 `previous_id` 与提交原文 |
| 邻段展开 | 序号 2 进入上下文、序号 3 被最终判断引用 → 返回 1..3，标志分别为 (F,F)、(T,F)、(F,T) |
| 只读性 | 调用 `evidence-context` 前后任务详情（含 `finished_at`）不变 |
| 来源未冻结 | `source_id` 为 `null`、`paragraphs` 为空（表示暂无内容，非来源不存在） |
| 已冻结但无锚点 | 来源已冻结而尚无候选或引用（任务在 `query_generation` 阶段失败即此形态）时，`source_id` 有值而 `paragraphs` 为空——评审补充的第三种组合 |
| 不越源 | 跨来源的段落标识经 `read_neighbors` 解析为空 |
| 邻段不是证据 | `ContextParagraph` 不带 `validation` 字段；列表按 `ordinal` 升序，但**列表相邻不等于原文相邻**，判定只能用 `after.ordinal == anchor.ordinal + 1`（Issue #47） |
| 四条终态路径时间戳 | 完成、排队取消、总超时、遗留 `RUNNING` 结算，均满足 `updated_at == finished_at` |
| worker 循环活下去 | 首轮 `run_once` 抛 `RuntimeError` 后循环仍在领取（`calls > 3`），并记录 `Worker loop iteration failed; continuing` |
| 工厂抛异常落终态 | 已领取任务落 `FAILED`、`error_code is None`、`finished_at` 非空，且不可重复领取 |
| 冻结摘要重提边界 | 有效配置未变时，用 `/input` 的冻结摘要重提被接受（`202`）；配置改变后同一摘要被拒（`409`、`error_code=null`、固定文案「配置已更改，请重新预览并确认」） |

### 端到端联调后端缺口：未覆盖

- 两个只读投影都只对**本机记录**做投影，未接入真实来源或模型；**前端已有调用方**（自 PR #37 合入 `add34f8` 起）：`frontend/src/api/contracts.ts:235` / `:236` 的 `getCheckInput` / `getEvidenceContext` 已由 `frontend/src/api/http.ts:40` / `:41` 实现（对应 `/input`、`/evidence-context`），任务详情页 `CheckDetail.vue` 的调用点有三处：「原始提交」（`:40`）与「查看冻结上下文」（`:61`）两个披露面板，以及每条证据下的「查看邻段」（`:69`），都在展开时按需读取。本节原文记「目前无前端调用方……全仓也搜不到 `evidence-context` 的调用点」，那是 PR #37 合并前的状态，订正依据见下方「只读投影前端调用方订正（2026-10-14）」一节。
- **`evidence-context` 在真实来源上目前只能返回锚点自身**：真实 PMC 经 `metadataPrefix=pmc_fm` 取回的「全文」实际只含题录与摘要（`jats_bytes` 的 `<body>` 计数为 0，见 #28），该来源段落表仅 0~1 段，因此 `ordinal±1` 的邻段展开恒为空，「引文前后是什么」在当前冻结内容下无法兑现。此前写作「冻结样本仅 3 段」会让人误以为换成真实来源即可，属措辞不准；该项在 #20 中记为**阻塞**，随 #28 修复。
  > ⚠️ **2026-10-12 更新**：#28 已修复并合入 main（PR #29：PMC 取回先请求 `pmc`、仅在 `cannotDisseminateFormat` 时回落 `pmc_fm`，见下方「PMC 全文取回：metadataPrefix 修正」一节），本分支随本次合并已包含该修复。故上面「只能返回锚点自身」描述的是**修复前**的状态；邻段能力在真实来源上**是否恢复尚未复测**（本节用例仍只覆盖冻结样本），按 #20 清单复测前不声明为已验证能力。
- `evidence-context` 只按 `ordinal±1` 展开，不解析文内交叉引用（如「见第 2 节」），跨小节引用不在本次范围。
- worker 兜底只在**进程内**隔离单个任务失败。它不解决任务级挂起（无超时地卡在某个 await），也覆盖不到「存储层持续不可用」这类跨轮次故障。
- 时间戳一致覆盖**当前全部 4 处**终态写入点：全仓 `UPDATE tasks SET status` 仅 `finish`、排队取消、总超时、遗留 `RUNNING` 结算四处，均已复用同一 `_now()`（评审独立 grep 复核）。新增终态写入点需同步本用例，否则不在保护范围内。
- `/input` 未取得 `RUNNING` 态快照：自动化用例覆盖 `QUEUED`；`BLOCKED` 为评审手工复核（无对应用例）；`RUNNING` 因 worker 领取间隔与轮询起点错开未抓到，已记入 #20。
- 最小密钥说明为文档描述，本次无可用密钥，未在真实上游端点下跑通一次完整核验。

### 评审修正（2026-10-12）

评审（lvyixi1110）复核后指出 `CheckInput` 的必要性论证与事实不符、且该接口当前无前端调用方；逐条复核属实并修正（对象提交 `3a53dc37b3c2dc6446a46ce793d9816466c108bb`）：

| 评审项 | 处理 |
| --- | --- |
| `CheckSummary.doi` 早已覆盖提交 DOI，前端 `originalDoi` 已从历史行回退取值 | docstring 与两份文档改为准确口径，不再声称本接口是唯一路径 |
| 冻结 `config_digest` 不是重提应发送的值 | 文档写明语义，并新增边界用例固化「配置未变放行 / 配置变更 409」 |
| `source_id` 有值而 `paragraphs` 为空是第三种组合 | `architecture.md` 与本节补记 |
| 时间戳未覆盖措辞偏保守 | 改为「覆盖当前全部 4 处终态写入点」 |
| `RUNNING` 态未覆盖 | 记入本节与 #20 |
| 未装前端依赖的失败形态 | `development.md` 写具体：`tests/boundary/test_frontend_shapes.py` 整组失败（检查器找不到 `typescript`） |
| `contracts.ts` 两个新 interface 是死代码 | 两处标注「尚无客户端方法调用」 |

### 评审修正（第二轮，2026-10-12）

第二轮评审（lvyixi1110）指出首轮修正未收口：同一「唯一路径」前提仍留在 `tests/tools/test_checks_api.py` 与本节的过期记录里；另指出时间戳用例在本机时钟分辨率下近乎恒真。逐条处理后记录如下（对象提交为本 PR 在 `3687b9f` 之上的两次提交 —— 口径修正与用例硬化，本记录随后单独提交以避免哈希自指）：

| 评审项 | 处理 |
| --- | --- |
| B1 用例 docstring 仍是旧前提（「只能靠本接口」） | 与 `api/app.py`、`domain/contracts.py` 的口径对齐：说明这是**详情视图**的空窗（DOI 只在 `source` 里、`source` 在来源身份解析成功前为 null），本接口是按任务直接读取并给出冻结授权范围，且**并非**取得提交 DOI 的唯一路径（历史行 `CheckSummary.doi` 与 `originalDoi` 已覆盖） |
| B2 同一用例的行内注释仍是同一口径 | 改为「同一时刻的详情视图给不出 DOI —— 这是详情视图在该阶段的空窗」 |
| B3 本节有一行因首轮修正而过期 | 删去「`/input` 的文档字符串点名 `QUEUED, RUNNING, BLOCKED` 三态」半句（该措辞已在首轮改掉） |
| B4 同一行把「评审手工复核」写成「测试覆盖」 | 改为「自动化用例覆盖 `QUEUED`；`BLOCKED` 为评审手工复核（无对应用例）；`RUNNING` 未覆盖」 |
| 时间戳用例在 Windows 上近乎恒真（非阻塞） | 采纳评审建议 1：用例内把 `sqlite._now` 换成自增计数，使「同一处复用」仍相等而「两次取钟」必然不等，断言脱离时钟分辨率 |

#### 评审修正（第二轮）：实际检查

环境：Windows、Python 3.12.14、pytest 9.1.1；Node v22.22.2。后端全量前已装齐 `requirements.lock`（含 `litellm` 及其传递依赖），前端已有 `node_modules`。

| 检查 | 结果 |
| --- | --- |
| `pytest ../tests -q`（全量） | **248 passed，3 warnings**（86.21s），无回归 |
| `pytest ../tests/tools/test_checks_api.py -q` | **30 passed** |
| `pytest ../tests/boundary/test_storage_lifecycle.py ../tests/boundary/test_domain_contract.py -q` | **31 passed** |
| `pytest ../tests/tools/test_api_contract.py ../tests/boundary/test_frontend_shapes.py -q` | **16 passed**（OpenAPI / 架构文档 / 前端契约三方一致） |
| 前端 `node --experimental-strip-types --test tests/*.test.mjs` | **41 passed** |
| 前端 `npm run build`（`vue-tsc --noEmit` + `vite build`） | 通过，29 modules transformed |
| 时间戳用例的检出力（变异验证） | 把 `finish()` 的 `stamp, stamp` 退回 `_now(), _now()` 后该用例**失败**（`AssertionError: t1` / `assert 'tick-7' == 'tick-8'`）；恢复后通过。硬化前该断言在本机约 1/400 才检出，硬化后稳定检出 |

一处环境注记：首次跑全量时出现 6 个与业务无关的失败，来源是执行环境的沙箱拦截了用例对临时目录的删除（`[safe-delete]`），换一次运行即得 248 passed；两条结果均为实际执行记录。

> 合并 main 后复跑：本分支随后合并 main（PR #24「语义验收报告口径」、PR #29「PMC 取回修正」），全量用例由 248 增至 **264 passed**（本分支 248 + PR #24 的 13 + PR #29 的 3，集合互不重叠）；上方诸数字是第二轮（尚未合并 main）的实测快照，判读时以合并后的 264 为准。

## 语义验收报告口径（2026-10-12）

| 项目 | 记录 |
| --- | --- |
| 关联 | 测试方案「功能准确性」的「报告」条目，分母与对账规则取自 [评测口径](evaluation.md#4-质量指标) |
| 环境 | Windows、Python 3.12.13，`backend/.venv` 由 uv 创建，依赖按 `backend/requirements.lock` 安装 |
| 对象 | `tests/functional/report.py`、`tests/functional/test_report_metrics.py`（新增）；`tests/functional/conftest.py` 提取 `run_case`；产出 `docs/semantic-report.md` |

此前 PR #22 只产出「逐例通过」，没有任何指标数字，而测试方案要求报告摘录定位、语义正确情况、各类 precision/recall 与可判定覆盖率。本节补齐该口径。

### 语义验收报告口径：实际检查

| 检查 | 结果 |
| --- | --- |
| `pytest ../tests/functional -q` | **32 passed**（19 既有 + 9 报告口径 + 4 本轮复核修正） |
| `pytest -q`（全量） | **252 passed，2 warnings**（239 既有 + 13 本 PR），无回归 |
| `python report.py` | 生成 `docs/semantic-report.md`，N 由样本数派生；正文不含随 commit 变化的字段，溯源改用样本集指纹 `sha256:3035a7030a983d95`，生成时的 commit 只打印到 stdout 并由本记录登记 |
| 互斥恒等式 | `D+I+B+F+C+X+U = 7 = N`，报告内自带校验行 |
| 零分母记 N/A | 真值可判定子集为空时 `coverage_truth_decidable` 为 `None`，渲染为 `N/A`；`ratio(0,0)` 与 `ratio(3,0)` 均为 `None` |
| 真实零不被写成 N/A | 真值可判定子集有 1 槽位而系统未判断时，`0/1 = 0.0` 如实报出 |
| 拒判与失败留在召回分母 | 真值为相矛盾但拒判或失败 → 计入该类 FN，`recall = 1/3` |
| 无确定判断时摘录定位 | 写「不适用」，不写 100%；同时 `locatability` 为 `None` |
| macro-F1 排除零分母类 | 只有「支持」有样本时，另两类为 `None`，macro-F1 只由「支持」参与并报告参与类别 |
| 应拒判集合 R 的比率 | R 中无 COMPLETED 时 `r_error_rate` 为 `None`，不补成 0 |
| U>0 时报告为暂定 | 存在未结算槽位时报告含「暂定」字样，不发布最终结论 |
| 误判与过度拒判分列 | 两者各自单独计数，不只报条件准确率 |
| 正文样本数与 metrics 一致 | 第 0 节的 `N` 由 `m['total']` 派生，正文不再出现与 `N` 冲突的写死计数（旧文案的「首版 n=1 单次抽样」与同节 `N = 7` 打架）；新增用例断言正文不含 `n=1`/`n=7` 字面量 |
| macro-F1 参与类别顺序 | 按 `DEFINITIVE` 顺序（支持、部分支持、相矛盾）列出，与上方 F1 表一致；不再用 `sorted()` 按 Unicode 码位排成「支持、相矛盾、部分支持」 |
| 报告可逐字节复现（`--check`） | 报告正文不含 `git rev-parse` 得到的基线，改记样本集指纹；`python report.py --check` 实测输出「与重新生成的结果逐字节一致（N=7）」并以 0 退出。此前正文写 `git rev-parse --short HEAD` 并在工作区脏时标注，该值随 commit 变化，任何「重新生成后比对」的 CI 检查都会恒红 |

### 首次生成的数字（N=7，构造样本）

可判定覆盖率（全批次）85.7%（6/7）、真值可判定子集 100%（6/6）、摘录定位有效率 100%（6/6）、四类 precision/recall 均为 1.00、macro-F1 1.00、应拒判样本错误确定判断率 0%（0/1）。

**这些数字不得当作总体准确率**：样本是人工构造的，N=7 单次抽样，且真值单人标注无第二人复核。

### 语义验收报告口径：未覆盖

- **来源匹配准确率、证据 Recall@k** 需要独立基准与采样协议，本验收集不产出，报告内列为未覆盖而非填 0。
- **不确定区间**需要采样协议，N=7 不估计。
- 报告只覆盖参赛首版有限验收集，与 [评测口径](evaluation.md) 的正式研究评测（120 对）不是同一层，不互相替代。
- 报告由脚本生成，**已在 CI 中启用比对（2026-10-15）**：此前因正文含随 commit 变化的基线行而无法成立；报告改为逐字节可复现后，`.github/workflows/ci.yml` 的 `backend` 作业新增一步 `python tests/functional/report.py --check`（放在 `Run pytest` 之前），提交的报告与重新生成结果不一致时以非零码退出。该步是既有 `backend` 作业里的一步，**检查项总数不变（仍是三个）**，故 README 的「三个检查」表述仍然成立。本步的未覆盖：它只保证报告与**同一份冻结样本**一致，样本集本身是否可信（真实来源、第二人复核）不在其保护范围内——样本改动后仍须重新生成报告，否则本步会红。

## PMC 全文取回：metadataPrefix 修正（2026-10-12）

| 项目 | 记录 |
| --- | --- |
| 关联 | Issue #28（本缺陷）；#20 清单中 `evidence-context` 邻段能力的阻塞项 |
| 环境 | Windows、Python 3.12.13（`backend/.venv`，uv 创建）、Node 22.22.2 / npm 10.9.7 |
| 对象 | `backend/paper_evidence/sources/pmc.py`、`tests/tools/test_sources.py` |

### PMC 全文取回：缺陷与根因

`fetch_record` 使用 `metadataPrefix=pmc_fm`。`pmc_fm` 是 PMC **F**ront **M**atter：返回的 `<article>` **不含 `<body>`**，只有题录、摘要与许可。于是冻结进 `SourceSnapshot` 的「全文」实际只有摘要，`parse_jats` 按设计回落到 `<abstract>`。

后果有两个：

- 系统只能据摘要判断论断，正好命中 `docs/prd.md` 明令禁止的「用摘要代替全文来声称全文没有相关证据」；
- PR #27 新增的 `GET /api/checks/{id}/evidence-context` 的 `ordinal±1` 邻段展开在真实来源上**恒为空**——不是样本规模问题。

上一节「PMC OAI 取回链路修复」曾判定「`pmc` 对多数记录返回 400 `cannotDisseminateFormat`，只有 `pmc_fm` 返回完整 JATS 正文」。该判断与实测相反，已在该节就地标注修正（保留原文以说明当时的依据）。

### 实测对照（live PMC，3 个 CC BY 记录，2026-10-12）

| metadataPrefix | PMC1182327 | PMC8806060 | PMC7461750 |
| --- | --- | --- | --- |
| `pmc_fm` | `<body>` 计数 **0**，`<p>` 4 | `<body>` 0，`<p>` 3 | `<body>` 0，`<p>` 0 |
| `pmc` | `<body>` **1**，`<sec>` 8，`<p>` 38 | `<body>` **1**，`<sec>` 20，`<p>` 57 | `<body>` **1**，`<sec>` 0，`<p>` 6 |

### PMC 全文取回：修复

- `fetch_record` **先请求 `pmc`（正文）**；仅在 PMC 返回 OAI 错误码 **`cannotDisseminateFormat`**（记录不在 OA 子集）时，才回落到 `pmc_fm`。其它 OAI 错误照旧映射 `SOURCE_UNAVAILABLE`，且不做第二次请求。
- 请求与解析拆为 `_get_record()`，错误处理按 `error` 元素的 **`code` 属性**判定，不再按「是否存在 `error` 元素」一刀切。
- 就地订正两处与实测相反的说明：`pmc.py` 的常量注释、原测试的 docstring 与函数名（原名 `test_pmc_oai_request_uses_the_full_text_metadata_prefix` 断言 `pmc_fm`，前提本身是错的）。

### PMC 全文取回：实际检查

| 检查 | 结果 |
| --- | --- |
| `pytest -c backend/pyproject.toml -q`（全量） | **255 passed，2 warnings**（72.93s；合并 main `eb0e117` 后复测）。合并前本分支 head 为 **242 passed**（当时 main `373c0ca` 既有 239 + 本 PR 新增 3）；main 侧另有 PR #24 的 13 条，本 PR 的 3 条与之互不影响 |
| `pytest -c backend/pyproject.toml -q tests/tools/test_sources.py` | **30 passed** |
| 合并 main 后另一侧能力未被破坏 | `python tests/functional/report.py --check`（PR #24 引入）仍输出「与重新生成的结果逐字节一致（N=7）」并以 0 退出；前端 `node --test` **41 passed**、`npm run build` 通过 |
| 真实端到端（修复后的代码，live Crossref + PMC + OpenAlex） | `10.1371/journal.pmed.0020124` → `PMC1182327`、license CC BY、`<body>`=1、`<sec>`=8，**解析段落数 1 → 32**；`PMC8806060` → 55 段；`PMC7461750` → 5 段 |
| 首个 GetRecord 请求的前缀 | `metadataPrefix=pmc`；只有在收到 `cannotDisseminateFormat` 后才会发出第二个 `pmc_fm` 请求 |
| 非 `cannotDisseminateFormat` 的 OAI 错误（`idDoesNotExist` / `badArgument`，参数化两条） | 仍映射 `SOURCE_UNAVAILABLE`，且**不发起第二次请求** |
| 回落路径的产物 | 回落得到的 `jats_bytes` **不含 `<body>`**（断言固化，防止把题录当正文） |
| 许可门控未被改动 | 回落样例仍正常解析出 `CC BY`；`classify_license` 相关用例全部通过 |

### 未覆盖与遗留

- **OA 子集之外的记录仍然只有题录+摘要**，回落路径不报错。是否需要在这种情形下**阻断**（而不是据摘要做判断），是产品口径决定，超出本连接器的职责；本 PR 不做行为变更，已在代码 docstring 与 Issue #28 中点明。
- 三个样例都是 CC BY 开放获取，**没有抽样非 OA 记录的真实 `cannotDisseminateFormat` 响应体**（该分支由 mock 用例覆盖，不是实测）。
- `parse_jats` 的摘要回落行为本身未改；`evidence-context` 的邻段能力是否恢复，需在 #28 修复合并后按 #20 清单复测（本次只验证到「来源冻结后含 `<body>`」）。
- 前端与文档的 `13 个业务接口` 等口径不受影响（本 PR 不改接口）。

## 端到端联调前置基线与真实链路探测（2026-10-12）

| 项目 | 记录 |
| --- | --- |
| 关联 | Issue #20 端到端联调测试清单（真实后端）；测试方案「执行记录与当前边界」。**#20 上已有「端到端联调结果（第 1 轮）」**，用本地 OpenAI 兼容替身把主流程跑到 `COMPLETED`；本节不改写其结论，只补基线数字、环境前置与探测方法学提醒 |
| 环境 | Windows、Python 3.12.13（`backend/.venv`）、Node 22.22.2 / npm 10.9.7 |
| 对象 | 主工作树 `6a2ea8f`（分支 `test/semantic-report`）。该提交相对当时的 `origin/main`（`373c0ca`）只改 `docs/` 与 `tests/`，**运行时文件改动为 0**，故下列运行时结论对**当时的** main 同样成立。注意 main 其后已前进（`eb0e117` 并入 PR #24、`a919d5b` 并入 PR #29，后者改了 `sources/pmc.py` 的运行时代码），故「对 main 成立」的适用区间截至 `373c0ca`；各条运行时结论未在合并后的 main 上重放 |
| 隔离 | 后端以 `PAPER_EVIDENCE_DATA_DIR` 指向系统临时目录启动，未触碰默认 `backend/.paper-evidence`；本次未修改仓库任何文件 |

本节用于在开始 Issue #20 清单前，先钉住「基线是否绿」和「真实链路走到哪一步」，并确认无模型密钥时的可达范围。

按复核意见，本节同时把 README「当前状态」里已被实测推翻的「外部来源连通性尚未验证」收窄为「模型连通性与论文语义验收尚未验证」（见下表），使仓库内表述与实测一致；两处改动同属本 PR。

### 端到端联调前置基线与真实链路探测：实际检查

| 检查 | 结果 |
| --- | --- |
| 后端基线 `pytest -c backend/pyproject.toml -q` | **239 passed，2 warnings（66.02s）**，在本 PR head（`ee79e53` = `origin/main` + 本节文档改动）实测。**此前记的 248 取自 `6a2ea8f`，它含尚未合并的 PR #24 的 9 条报告口径用例（239 + 9 = 248），不是本分支或 main 的现值**，本行已按复核意见更正 |
| 合并 `origin/main` 后定稿复测（`pytest -c backend/pyproject.toml -q`） | **255 passed，2 warnings**（合并提交 `68ff1dc` 实测 42.29s；定稿复测 39.18s，同一代码树、仅文档差异）；= 合并后 main 现值（含 PR #24 的 13 条与 PR #29 的 3 条），本节为纯文档改动，无回归 |
| 前端基线 `npm --prefix frontend test` | **41 passed / 0 fail**。较 2026-10-11 记录的 42 少 1 条，来源已定位：#21（`373c0ca`）删除了 `frontend/tests/workbench.test.mjs` 中 `501 is explicit and never falls back to demo`（对应实现已随该 PR 移除），属用例随实现下线，非静默削弱断言 |
| `npm --prefix frontend run build` | 通过（`vue-tsc --noEmit` + vite build，29 模块；`dist/` 已在 `.gitignore` 中） |
| `python -m pip check` | No broken requirements found |
| `GET /health` | 200 `{"status":"ok"}`（连续三次复测） |
| `GET /api/run-config` | 200，`config_digest` 稳定；limits `3/1/2/1`、timeouts `45/15/180`、观测默认关闭 |
| `GET /api/checks`（空库） | 200 `[]` |
| 真实来源解析 `10.1371/journal.pmed.0020124` | 200，返回真实题名、作者、年份（**Crossref 与 PMC 实时链路可用**）。README「当前状态」原称「真实外部来源与模型连通性…尚未验证」，本 PR 按此实测把该句收窄为「模型连通性与论文语义验收尚未验证」 |
| DOI 格式非法 `not-a-doi` | 400 `DOI_INVALID` |
| 不存在的 DOI | 404 `DOI_UNRESOLVABLE` |
| 配置摘要过期（`config_digest` 不匹配） | 409「配置已更改，请重新预览并确认」，`error_code=null` |
| `source_confirmed=false` / `cloud_consent=false` | 均 400「需要同时确认来源与云调用授权」，不创建任务、不调用模型 |
| 空论断 | 400「论断不能为空」 |
| 创建合法任务（无模型密钥） | **202 / `QUEUED`**；历史列表含论断摘要与 `created_at` |
| 启动 worker（`--loop`）后任务推进 | `QUEUED → RUNNING → FAILED`，`stage=query_generation`，`error_code=UPSTREAM_UNAVAILABLE`，`label=null`，`decision=null` |
| 来源阶段实测（同一任务） | `source_identity` 成功（1077ms）、`fetch` 成功（2532ms）；取到 `PMC1182327`、`license=CC BY`、`version=1`、`version_hash`（sha256） |
| 调用账 | `verification=verified`，`main_requests_used=1`，`upstream_attempts_used=2`，`observed_upstream_attempts=2` |
| 失败任务诊断包（redacted） | 200，`schema_version=2.2`；`execution` 三段 span 带 stage/tool/status/error_code/duration_ms/request_id；`model_calls` 含 attempts |
| 逐次尝试记录 | attempt 1 `recovery_kind=none` → attempt 2 `recovery_kind=retry`（reason `UPSTREAM_UNAVAILABLE`），与「首次加一次恢复」一致 |
| 未知 usage 不写零 | `usage=null`、`verified_model_version=null`，未写成 0 或别名 |
| redacted 保留公开书目 | DOI、PMCID、题名、作者、license、version、access_url、version_hash 均保留；`input.claim` 为 `<redacted>` |
| 脱敏泄漏扫描 | 原句文本在整包中出现 **0** 次 |
| 语义导出：未配置诊断接收方 | 400「诊断接收方未获授权」 |
| 语义导出：缺 `semantic_export_consent` | 400「缺少语义导出授权」 |
| 反馈 | 200 `saved=true` |
| 重试（终态任务） | 202 新建任务，`previous_id` 指向原任务；沿用原句；**新任务重新计账（1 次主请求 / 2 次尝试），预算未继承** |
| 取消已终态任务 | 409「任务已结束，不能取消」，响应同时带 `status`/`stage` |
| 取消 `QUEUED` 任务 | 200 `CANCELLED`，`cancel_requested=true`，`label` 与 `decision` 均为 null |
| 重复取消 | 对已 `CANCELLED` 的任务再次 `POST /cancel` 仍返回 200，幂等，不报错 |
| 带 `previous_id` 重提（修改/拆分机制） | 202 新任务并记录关联；原任务输入未被改写；模型上下文不继承 |
| `previous_id` 指向不存在的任务 | 404「关联的原任务不存在」 |
| 无 worker 时任务不推进 | 不启动 worker 时任务停在 `QUEUED`，API 进程不自行执行 |
| 删除终态任务 | 200，历史列表随即不再包含该任务 |

### 未覆盖与阻塞

- **模型密钥缺失**：环境无 `PAPER_EVIDENCE_MODEL_API_KEY`，SDK 传输回落到 `PAPER_EVIDENCE_MODEL_BASE_URL`（默认 `http://127.0.0.1:4000`）后连接被拒，本次探测在 `query_generation` 止步。链路正确性已由 #20 第 1 轮的本地替身上游证明（主流程跑到 `COMPLETED`）；**该缺口已被后续实测补齐**——真实模型下的判断与证据校验已由 #20 第 2 轮（2026-10-14，上游 `deepseek/deepseek-flash`）跑通，本次探测缺的只是当时的环境密钥；**至今仍未完成的是论文语义验收**。替身或构造数据的结果不得用于声称语义验收通过。
- **Issue #20 清单未链接 worker 常驻要求**：API 进程自身不执行任务，不启动 worker 时任务会永远停在 `QUEUED`（本次实测确认）。该要求已写在 `docs/development.md` 第 58 行，但清单「前提」没有链接它，建议补一行，避免执行人误判为功能缺陷。
- 未做 UI 层验证：轮询可见性、加载中/断网/空历史三态、桌面 1440px / 平板 1024px / 窄屏 390px 布局均需真实前端，本次未覆盖。
- 未测在途任务的取消：本次只覆盖 **`QUEUED` 任务的取消**（含重复取消的幂等）与 **终态任务的取消拒绝分支**；**`RUNNING` 在途任务的取消、取消与完成的竞态仍未实测**。
- 探测本身在 `6a2ea8f` 的主工作树上进行（该提交相对 `origin/main` 只改 `docs/` 与 `tests/`，运行时文件改动为 0）；定稿时已在合并 `origin/main` 后的本分支 head 重跑全量（见上表「合并 `origin/main` 后定稿复测」一行）。但**各条运行时结论没有在本分支代码上重放**，其运行环境基线仍是 `6a2ea8f`。
- 语义报告 N=7 构造样本与单人标注的两条限制不变，本节不改变其口径。

### 复现方式（供 #20 执行人照抄）

```bash
# 1) 后端：用隔离数据目录启动，避免污染默认 backend/.paper-evidence
cd backend
export PAPER_EVIDENCE_DATA_DIR="${TMPDIR:-/tmp}/pe_e2e_probe"   # Windows 写具体路径，如 C:/Users/<you>/AppData/Local/Temp/pe_e2e_probe
.venv/bin/python -m uvicorn paper_evidence.api.app:app --host 127.0.0.1 --port 8000
# Windows 用 .\.venv\Scripts\python 代替 .venv/bin/python

# 2) 必须等端口 bind 完成再探测，否则 /health 可能得到伪造的 502
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)" = "200" ]; do sleep 1; done

# 3) 取当前配置摘要；创建任务时的 config_digest 必须用它
curl -s http://127.0.0.1:8000/api/run-config     # → config_digest

# 4) 另开一个进程常驻 worker：API 进程自己不执行任务，
#    不启动 worker 时任务会永远停在 QUEUED（不是功能缺陷）
#    两个进程必须指向同一个数据目录；否则 worker 会读默认的 backend/.paper-evidence，
#    与第 1 步的临时库不是同一个，任务同样会停在 QUEUED
cd backend && PAPER_EVIDENCE_DATA_DIR="${TMPDIR:-/tmp}/pe_e2e_probe" \
  .venv/bin/python -m paper_evidence.worker --loop --interval 1
```

关键请求与期望（`$DIGEST` 取自第 3 步）：

| 请求 | 期望 |
| --- | --- |
| `GET /api/sources/resolve?doi=not-a-doi` | 400 `DOI_INVALID` |
| `GET /api/sources/resolve?doi=10.9999/does-not-exist` | 404 `DOI_UNRESOLVABLE` |
| `POST /api/checks`，`config_digest` 用过期值 | 409「配置已更改，请重新预览并确认」，`error_code=null` |
| `POST /api/checks`，`source_confirmed=false` 或 `cloud_consent=false` | 400「需要同时确认来源与云调用授权」 |
| `POST /api/checks`，`claim=""` | 400「论断不能为空」 |
| `POST /api/checks`（合法、无模型密钥） | 202 + `QUEUED`；落后 worker 取走 → `FAILED`，`stage=query_generation`、`error_code=UPSTREAM_UNAVAILABLE`、`label=null` |
| `GET /api/checks/{id}/diagnostic-packet` | 200，`schema_version=2.2`；`usage=null`（不是 0）；原句出现 0 次 |
| `POST /api/checks/{id}/retry` | 202，新任务 `previous_id` 指向原任务；调用账重开，预算不继承 |
| `POST /api/checks/{id}/cancel`（终态任务） | 409「任务已结束，不能取消」 |
| `POST /api/checks/{id}/cancel`（`QUEUED` 任务） | 200 `CANCELLED`；重复调用仍 200（幂等） |
| `DELETE /api/checks/{id}` | 200，历史列表随即不再包含该任务 |

### 一条方法学提醒

首次探测 `GET /health` 曾返回 **HTTP 502「upstream connect failed … (os error 10061)」**，随后连续三次复测均为 200。原因是 uvicorn 尚未完成端口绑定，请求被前置链路拒绝。`/health` 的实现为直接返回 `{"status":"ok"}`，不具备产生该错误码的路径。**探测前必须等后端就绪，否则会得到伪造的 502**；记录时须先复测再判定。

## 验证记录标题去重与协作规范角色化（2026-10-13）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `0ccb753`（纯文档改动：`AGENTS.md` 与 `docs/verification.md`），不含代码；本节随后单独提交，避免提交哈希自指 |
| 关联 | Issue #33（#30 评审的三条后续）；分支 `docs/heading-dedup-and-roles`，按 [AGENTS.md](../AGENTS.md) 从 `617c48d`（main）新建独立工作树 |
| 环境 | Windows / Git Bash、Python 3.12（主工作树 `backend/.venv`）。本轮只改文档，未涉及后端与前端代码 |
| 改动 | 1）`AGENTS.md` 把「标题不得重名」从「追加时的子标题」扩到节标题与各级子标题，并写明角色到账号的对应只在「分工」一节维护；2）`docs/verification.md` 把 39 个重名标题改为带节名前缀的唯一措辞 |

### 标题去重：实际检查

| 检查 | 结果 |
| --- | --- |
| 标题抽取与重名统计（跳过围栏代码块，`#`~`####`） | 改动前 **72 个标题 / 40 个不同文本**（8 组重名）；改动后 **72 个标题 / 72 个不同文本，无重名** |
| 重名明细（改动前） | `实际检查`×16、`未覆盖`×7、`覆盖与限制`×5、`失败与修复过程`×3、`缺陷与根因`×3、`未覆盖项`×2、`覆盖`×2、`修复`×2 |
| `git diff --numstat` | `docs/verification.md` 39 增 39 删。逐行核对 39 组改动**全部落在标题行**，正文一行未动 |
| 行尾与编码 | 改动前后均为 CRLF、UTF-8 无 BOM，总行数 791 不变 |
| 锚点失效风险 | 全仓搜索 `verification.md#` **无命中**；文档内对其它小节的引用用的是 `##` 节名（如「PMC 全文取回：metadataPrefix 修正」），该节未重命名，引用仍有效 |
| 其它文档 | `docs/test-plan.md` 13/13、`docs/semantic-report.md` 11/11、`README.md` 7/7、`AGENTS.md` 7/7，均无重名 |
| `git diff --check` | 无空白错误 |

### 标题去重：未覆盖与已确认的边界

- 本次只重命名**重名**标题，未改写本来唯一但未带节名前缀的子标题（如 `### 已知限制`、`### 一条方法学提醒`）。规则对新增内容要求带节名前缀，存量唯一标题保持原样，因此文档内标题风格尚未完全统一。
- 未用 Markdown 渲染器核对锚点跳转（本机无该检查器）；判定依据是全仓没有任何地方引用本文件的标题锚点。
- 新标题由「原节名 + 原小节名」拼成，未调整任何小节的归属或内容顺序；本次改动不改变各节记载的结论。

## README 归属规范补充（2026-10-13）

| 项目 | 记录 |
| --- | --- |
| 关联 | Issue #33 第 2 条（#30 评审的后续三条之一）；本条先由测试侧在 issue 中给建议措辞，作者确认后落地 |
| 改动 | `AGENTS.md`「验证与交付」补一行：`README.md` 中下结论式的状态描述（`## 当前状态` 一节，以及「尚未验证」这类能力判定）与 `docs/verification.md` 同属测试侧结论，须由测试负责人提交或明确复核；`README.md` 的`环境要求`、`快速开始`、`开发检查`、`持续集成`、`文档`等说明性内容不受此限 |
| 定价依据 | `README.md` 的`## 当前状态` 在 PR #25 里已由测试侧改写，现状已倾向测试侧，只是规范未写明；原规范只覆盖 `docs/verification.md` 与 `docs/semantic-report.md`。Issue #33 中我给出措辞与依据并请作者确认，作者回复「README『当前状态』这类下结论式的表述交给测试侧维护」 |

### README 归属补充：实际检查

| 检查 | 结果 |
| --- | --- |
| `README.md` 的节标题 | `## 当前状态`、`## 环境要求`、`## 快速开始`、`## 开发检查`、`## 持续集成`、`## 文档`；措辞点名 `## 当前状态`，其余按节名逐一列举，未用「文档索引」这类 README 中不存在的叫法 |
| `git diff --numstat`（`AGENTS.md`） | 1 增 0 删，仅插入一行 |
| 行尾与编码 | `AGENTS.md` 与本节均为 CRLF、UTF-8 无 BOM，与原文一致 |
| 标题唯一性 | 本节三个标题经抽取（跳过围栏代码块）后与全文比对，无重名 |

### README 归属补充：未覆盖与已确认的边界

- 本行只规定**归属**（由谁提交或明确复核），不改变 README 的内容口径；README 的措辞是否准确仍按一般评审流程判断。
- 未回溯已合并历史：本行生效前 README 的历史改动不受影响，与 `AGENTS.md` 既有的不回溯条款一致。
- 未在本次改动中修改 `README.md` 本身：该文件当前的内容仍取自 main，归属变更只影响后续改动由谁提交。

## 性能维度落地（tests/performance，2026-10-13）

| 项目 | 记录 |
| --- | --- |
| 关联 | Issue #26（补齐「性能」与「端到端」两个缺失维度）的性能一半；过程中发现并另开 Issue #31 |
| 环境 | Windows、Python 3.12.13（`backend/.venv`，uv 创建）、Node 22.22.2 / npm 10.9.7 |
| 对象 | 新增 `tests/performance/`（`fixtures.py`、`harness.py`、`measure.py` 与三个用例文件，共 21 条用例）。**不改** `backend/paper_evidence/` 与 `frontend/src/` 的任何行为 |
| 基线 | 从 `origin/main` = `a919d5b` 新建分支 `test/performance-dimension`；“基线 255 passed”指未加本目录时的全量结果 |

### 性能维度覆盖的判定

| 测试方案条目 | 落地方式 |
| --- | --- |
| 单进程、一次一个任务 | 一条 `run_once` 只领取一条；`drain` 顺序处理，并发峰值恒为 1；多 worker 下的独占另由存储层守卫兜底（PR #43，见本文「多 worker 不变量落地后的文档订正」一节） |
| 再提交任务时后来的停在 `QUEUED`、不另起执行器 | 在途任务被闸门挡住时提交第二条：仍是 `QUEUED`，工作流实例数不增加；放开后由同一条常驻循环接着处理 |
| 总时限自 RUNNING 起算、不含队列 | 队列里停放 600 秒后再领取，断言工作流收到的到期时刻 = 领取时刻 + 180，落库的挂钟到期时刻同源 |
| 45 / 15 / 180 秒三档与「剩余时间截短单次超时」 | 虚拟时钟：`timeout_for` 取 `min(45, 剩余)`；来源请求取 `min(15, 剩余)`；时钟走完直接 `TASK_TIMEOUT`，不发上游请求 |
| `Retry-After` 大于剩余时间不再重试 | 来源侧实测：只发 1 次请求、报 `UPSTREAM_TIMEOUT`，且不真的等待；反面用例覆盖「未超过剩余时间」照常退避重试 |
| 取消中断退避 | 退避等待期间取消任务，`CancelledError` 原样抛出、只发出 1 次请求 |
| 记录单任务延迟、逻辑请求数、上游尝试数及 token（缺失标为未知） | `measure.py` 从 store 已落库的行读数；缺失的 token 记为未知而非 0，并保留 `attempts_reporting/attempts_total` 作为分母 |

虚拟时钟只替换 `worker/runner.py`、`graph/workflow.py`、`models/recording.py`、`sources/http.py` 这四个模块命名空间里的 `time` 引用，业务代码未改动，也没有为可测性加注入口。`models/sdk.py` 与 `models/gateway.py` 故意不在替换集合内：导入 sdk 会连带加载 LiteLLM，为每个用例加十几秒；这两条传输的时钟用法由 `tests/tools/` 在真实时钟下覆盖。

### 性能维度实际检查

| 命令 | 结果 |
| --- | --- |
| `pytest -c backend/pyproject.toml -q tests/performance` | **21 passed**（5.23s） |
| `pytest -c backend/pyproject.toml -q`（全量，本分支） | **276 passed，2 warnings**（47.57s）＝ 基线 255 + 本维度 21 |
| 变异测试：`AttemptRecorder.timeout_for` 去掉 `min(..., remaining)` | 对应用例失败（1 failed） |
| 变异测试：`Fetcher` 去掉 `min(self._request_seconds, remaining)` | 对应用例失败（1 failed） |
| 变异测试：`runner.run_once` 的 deadline 改成领取后多给 600 秒 | 对应用例失败（1 failed） |
| 变异测试：`_accounting` 在缺少尝试记录时也写 `upstream_attempts_used` | 对应用例失败（1 failed） |
| 前端 | 本 PR 未改前端；未运行前端检查 |

### 性能维度未执行与未覆盖

- **四条本机集成验收未执行**：取消接口 1 秒内响应、受理后 2 秒内收尾释放 worker、deadline 后 2 秒内收尾，以及无负载前提本身。它们需要 API 与 `--loop` worker 双进程同时运行、且任务在途足够久——无密钥时任务在 `query_generation` 立即以 `UPSTREAM_UNAVAILABLE` 收口，测不到释放路径。**未跑，不记为通过。**
- **真实上游下的性能数字未测**：单任务延迟、逻辑请求数、上游尝试数、token 的口径已被用例钉住，但本次喂给它们的是构造记录，不是真实模型。测试方案要求性能数字在真实上游下测量才有意义，因此本记录不含任何性能结论。
- **多 worker 并发：判定已移交边界维度**：`SqliteStore.claim_next` 原先只按 `QUEUED` 取队首、**不检查是否已有 `RUNNING`**，所以「一次一个任务」当时由单进程 worker 的顺序循环保证，属于运行约定而非存储层约束，两个 worker 进程会各领一条并行执行。PR #43（合并为 `f051ce0`）把它改成了**存储层不变量**：只要有一行处于 `RUNNING`，领取就返回 `None`，遗留 `RUNNING` 也只在**自己时限已过**时结算，第二个 worker 的启动不再会杀掉在途任务。本维度按测试方案的「保持单进程」前提仍不做该场景的判定，判定改由 `tests/boundary/test_worker_exclusivity.py`（10 条；本文记这一栏时是 8 条，PR #46 新增 2 条）承担，依据见本文「多 worker 不变量落地后的文档订正」与「#46 覆盖残留的结论订正」两节。
- **模型侧 `Retry-After` 规则未在本维度重复**：已由 `tests/tools/test_sdk_gateway.py` 在真实时钟下覆盖，本维度只补来源侧同一规则与确切边界。
- **本机无负载前提未验证**：所有耗时断言都刻意宽松（或因虚拟时钟而确定），没有测量机器背景负载。
- **端到端维度（`tests/e2e/`）仍缺**：属 Issue #26 的另一半，需先定 Playwright 归属与浏览器环境。

### 性能维度过程缺陷

新增 `tests/performance/conftest.py` 会让 `tests/functional` 的 8 条用例 ImportError（裸 `from conftest import ...` 解析到别的目录）。已按「新增维度不放 conftest」落地，根因与三种修法见 Issue #31。

## 端到端维度：界面主路径（2026-10-13）

`docs/test-plan.md` 第 120 行把界面主路径放在 `tests/e2e/`，用 Playwright 覆盖确认来源、同意整次任务的接收方/数据范围/预算、查看 paper agent 的判断与原文位置，以及澄清重提、取消排队与运行中的任务、显示超时与书目导出预览、删除本地记录。这一节记录该维度的落地方式与实测结果；它是**补齐一个整维度缺失**，不替代其他各维的判定。

### 端到端维度的落地

- 依赖自持：`tests/e2e/package.json` 固定 `@playwright/test` 1.64.0，**不改** `frontend/package.json` / `package-lock.json`，避免把测试依赖塞进产品依赖。引入 Playwright 的归属协调见 Issue #26。
- `playwright.config.ts` 的 `webServer` 一次起四个进程：本机上游替身（8765）→ 真 API（8000）→ 常驻 worker（就绪信标 8001）→ 前端 dev server（5173）。端口是硬约束而不是自由参数：`frontend/vite.config.ts:6` 把 `/api`、`/health` 固定代理到 8000，前端 dev server 固定 5173。`reuseExistingServer` 刻意关掉——复用可能是使用者自己的真实后端，那会让用例打到真实上游，而避免这一点正是本维度的目的。
- 上游全部换成替身（`tests/e2e/support/upstreams.py`，stdlib `ThreadingHTTPServer`）：Crossref 元数据与 agency、DOI 解析探针（302）、PMC idconv、PMC OAI-PMH 的 GetRecord（含真 JATS 的 `<article>`）、OpenAlex 线索，外加一个 OpenAI 兼容的 `/v1/chat/completions`。`POST /_stub/delay`、`POST /_stub/mode` 让用例按需制造「任务在途」与「上游不可用」，不必重启进程。
- 两个 Python 进程必须拿到**完全一致**的 `Settings`：提交时 API 用提交的 `config_digest` 与自己的快照比对（`api/app.py:403`），所以来源地址与 `timeouts` 共用一份构造（`support/runtime.py`）。单次模型尝试上限调到 8 秒，只为让「上游超时」用例不必真等 45 秒；两个进程同值，快照仍自洽。
- 任务库的「空」起点由**每轮新建数据目录**保证，不在启动脚本里删上一轮的库：四个 `webServer` 并发启动，worker 可能先一步打开 SQLite，后启动的进程再 `unlink` 就撞上文件锁（实测 `PermissionError: [WinError 32]`）。轨迹与报告同样按轮次分目录，避免 Playwright 启动时去清上一轮的成百个轨迹文件。
- 按 Issue #26 定下的口径（2026-10-13）：Playwright 依赖由 `tests/e2e/` 自持，**不并入** `frontend/package.json`；`.github/workflows/ci.yml` 增加独立的 **`e2e` 检查项**，该作业装后端依赖与前端依赖（用例要起真前端 dev server）、`cd tests/e2e && npm ci`、`npx playwright install --with-deps chromium` 后跑 `npm test`，失败时上传整轮运行目录 `tests/e2e/.run/` 供定位（轨迹、HTML 报告，以及常驻 worker 自己写的那份 `worker-<runId>.log`）；`.run/` 是隐藏目录，作业里必须开 `include-hidden-files`，`if-no-files-found` 取 `warn` 以便真收不到产物时留下告警。`PAPER_EVIDENCE_E2E_PYTHON` 在该作业里指向 setup-python 装到 PATH 上的解释器。该作业在 `ubuntu-latest` 上的**首次结果是失败**（13 条里 3 条通过、10 条卡在「排队中」），根因在测试脚手架自身、与产品实现无关，见「端到端维度的过程缺陷」第 4 条；修复后第二次运行 **13 passed（54.3s）**，作业总时长 1m49s。

### 端到端维度的前置

- Node 侧：`cd tests/e2e && npm ci && npx playwright install chromium`。工作树里还需要 `frontend/node_modules`（前端 dev server 要用），它不在 git 里。
- `PAPER_EVIDENCE_E2E_PYTHON` 指向后端解释器。默认按 `backend/.venv` 找；本机复现时后端 venv 只在主工作树，所以显式指定。
- **不需要模型密钥**：模型网关同样由替身充当，用例不访问网络。这是本维度与 `tests/functional/` 真值判定的分界。
- 运行前 8000 / 5173 / 8765 / 8001 必须空闲。回环地址必须排除在代理之外，理由见下面的过程缺陷第 1 条。
- 本机跑后端全量时要显式给 `--basetemp=<新建目录>`：pytest 收尾清理旧的编号临时目录时会在一次调用里删掉上百个文件，被这台机器的批量删除保护拦下，导致退出码为 1（用例本身全绿）。属于本机环境处置，不改仓库配置。

### 端到端维度实际检查

| 检查 | 实际结果 |
| --- | --- |
| `npx playwright test`（chromium，串行，13 条） | **13 passed（1.6m）**；连续三次运行结果一致，且输出中没有替身侧异常堆栈。第三次是在**合并 main（含 #25/#27/#30）之后**跑的，所以这一维度在 main 当前状态下同样成立 |
| 用例分布 | `01-shell` 2 条（空态与真实接口模式、无效链接回落）、`02-main-path` 4 条（提交前必看项、跑完渲染判断与原文位置、刷新读回、运行诊断）、`03-cancel` 1 条（RUNNING 与 QUEUED 两个取消分支）、`04-upstream-timeout` 1 条、`05-diagnostics` 2 条（脱敏包明示书目未遮盖与语义导出单独授权、诊断页深链）、`06-revise-and-delete` 3 条 |
| 本机浏览器 | Playwright 1.64.0 自带的 Chromium（HeadlessChrome 156.0.8078.4）实测可用，**推翻了 Issue #26 里「本机浏览器不可用」的旧结论**（该结论来自 `agent-browser` 返回 empty page 的尝试） |
| 判定对象 | 界面行为与状态流转：状态的可见文案、按钮可用性、路由、渲染出的摘录与段落标识、调用账数字 |
| 两条按设计真等时间的用例 | `03-cancel` 约 21.7s、`04-upstream-timeout` 约 10.9s；其余 11 条各在 0.7–5.4s 之间 |
| 既有的一侧未被破坏 | 合并 main（含 #25/#27/#30）后：后端全量 `pytest -c backend/pyproject.toml -q --basetemp=<新建目录>` → **264 passed，2 warnings**（97.40s，退出码 0）；前端 `npm test` → **41 passed**、`npm run build` 通过。本 PR 不动后端与前端代码，这两项只证明新目录没有影响既有用例的收集与运行 |
| CI 的 `e2e` 作业（`ubuntu-latest`） | 第一次运行**失败**（13 条里 3 条通过、10 条卡在「排队中」，根因是测试脚手架自己删了本轮的任务库，见「端到端维度的过程缺陷」第 4 条）；修复后第二次运行 **13 passed（54.3s）**，作业总时长 1m49s，同一次运行的 `backend` 与 `frontend` 均 success。Linux 比本机快：本机同一套 1.7m |

### 端到端维度的过程缺陷

1. **回环地址被环境代理劫持，四个 `webServer` 一个都起不来（已修）。** 现象是 `Error: Timed out waiting 60000ms from config.webServer`。`DEBUG=pw:webserver` 显示 `127.0.0.1:8000/health` 在进程起来后持续返回 **404**，而同一时刻用 `curl --noproxy` 拿到的却是 `200 {"status":"ok"}`。根因是两条路径都读代理环境变量：Playwright 的就绪检查经 `WebServerPlugin` → `isURLAvailable` → `httpRequest` → `proxy-from-env` 把请求发给 `HTTP_PROXY`（本机为 `http://127.0.0.1:62800`），而该透明代理对回环端口的应答并不等于目标进程的应答；后端用的 `httpx.AsyncClient()`（`api/deps.py:47`）默认 `trust_env=True`，同样会把查来源的请求交给代理。修法是在配置层把回环摘出代理（`NO_PROXY` 管探活 + 四个代理变量置空后传给子进程），并已在配置里写明原因。对照实测：同一请求带代理 404、不带代理 200。
2. **首次运行有三条用例失败，全部是用例自己的问题，不是产品缺陷（已修）。** 记录在此以免被误读成实现缺陷：
   - `02-main-path`「跑完」一条断言 `details.disclosure dl.facts` 里没有「未知」，但详情页的**费用**一栏按口径固定显示「未知」（`CheckDetail.vue:37`，因为调用次数不是费用上限、本机替身也不提供计费）。改为按 `dt` 精确取值，逐个断言创建/开始/结束三个时刻已落定，并把「费用=未知」转成正面断言。
   - `02-main-path`「运行诊断」一条断言尝试行不出现「未知」，但该表第 4 列是**模型版本**，而 `verified_model_version` 在无法验证版本时按口径就是 `null`（`docs/glossary.md:230`、`docs/verification.md:391`），界面显示「未知」是正确行为。改为列级断言：Tokens 列是替身声明的 `33`，模型版本列是「未知」。
   - `06-revise-and-delete`「修改原句」一条漏了「重新读取来源并重新授权」这一步：`workbench.ts` 的 `prepareEdit` 只把 DOI 与原句带进新草稿，`source`/`config` 被清空，`canSubmit` 因此不成立，提交按钮保持禁用。用例补上 `readSource` + `authorize`，并把「草稿里没有来源预览」写成正面断言。
3. **替身按预期吞掉落线，但仍会把断开打成完整 traceback，刷掉用例输出（已修）。** 应用在超时或取消时主动断开上游连接是**被覆盖的行为**（`04-upstream-timeout`、`03-cancel` 正是靠它成立），`BaseHTTPRequestHandler` 却把它当异常记录。替身改为吞掉 `ConnectionError`，并在代码里注明这不是替身故障。
4. **配置里的「清理上一轮数据目录」把本轮正在用的库删掉了，这是本维度在 Linux 上第一条就挂的原因（已修）。** 现象来自 Issue #26 的 `e2e` 作业第一次在 `ubuntu-latest` 上运行：13 条里 3 条通过、10 条失败，且 10 条的失败点完全相同——`helpers.ts:84` 的 `expectStatus` 在 15 秒里始终解析到 `<span class="status-label queued">排队中</span>`，也就是常驻 worker 没有消费队列。失败现场起初一个字节都没留下：`upload-artifact` 默认跳过隐藏文件，`.run/` 是隐藏目录，作业报的是 `No files were found with the provided path`；补上 `include-hidden-files: true` 之后产物才到手。
   根因放在 `playwright.config.ts` 的 `prepareRun()` 里：它每次评测都先删掉 `.run/data-*`。**这份配置在一次运行中会被评测多次**——runner 一次，每个测试 worker 进程各一次——而 `data-<runId>` 正是 runner 那次评测建出来、写进四个 webServer 环境的目录（失败那次 10 条用例落在 10 个不同的 `results-<runId>` 里，就是 10 次评测的直接证据）。删除因此发生在运行中途：POSIX 上 `rmSync` 成功，API 与常驻 worker 各自拿着一个已经 unlink 的库文件继续跑，worker 再也看不到 API 写进去的任务；Windows 上因为有进程占着库，`rmSync` 抛 `WinError 32`（正是原先注释里记的那个错）被 `catch` 吞掉，目录保住，**所以这个错只在 Linux 上暴露，本机三次全绿也照样盖不住它**。旁证是产物里**一个 `data-*` 目录都没有**，包括 API 重建的那份——API 的 store 在第一次请求时就已经缓存，不会因为路径被删而重开，于是两边各错各的、界面上始终只有 API 那一侧的数据。
   修法：清理搬出配置，改由 `npm test` 的 pretest（`support/clean_run.mjs`）执行，一次运行只跑一次、只删上一轮的目录。修复后在 `ubuntu-latest` 上重跑 **13 passed（54.3s）**（作业总时长 1m49s），本机 Windows 复测同样 **13 passed（1.7m）**，`.run/` 里本轮数据目录还在（另有 1 个空 `data-*` 来自第二次评测，属正常残留）；同时把常驻 worker 的 stdout/stderr 另存一份到 `.run/worker-<runId>.log` 并随产物上传——就绪端口只能证明「进程起过」，证明不了它还在消费队列，而 Playwright 默认把 webServer 的 stdout 丢掉。这份日志刻意不放在 `data-*` 下：那是 `prepareRun` 负责清理的一类，诊断文件不该跟着被测对象的生命周期走。

### 端到端维度未覆盖与已知限制

- **界面主路径的判定不构成论文语义结论。** 替身回的是构造数据（固定题名、固定摘录、固定「支持」标签），语义真值仍在 `tests/functional/` 的冻结样本与语义报告口径里。本维度的 13 条不能拿来当准确率或性能数字。
- **CI 上是独立检查项，暂不是合并必须通过。** 这是 Issue #26 定下的口径（先跑稳一段时间再考虑转为必需），所以本维度即使在 CI 变红也不阻断合并，需要靠评审看结果。`ubuntu-latest` 上首次运行失败、修复后第二次运行 **13 passed（54.3s）**，作业总时长 1m49s（含装依赖与装 Chromium）——比本机 Windows 的 1.7m 短。但这只是一次运行，距离「跑稳一段时间」还差得远，所以这条口径本次不动。该作业只在失败时上传产物（`if: failure()`），通过运行不留任何产物。
- **只覆盖 Chromium，且 headless。** 未覆盖其他浏览器、移动视口与有头模式；界面没有 `data-testid`，定位全靠可见文案与元素 `id`，文案改动会同时改动用例。
- **没有真实模型调用。** 因此「界面显示真实模型的判断」只验证到渲染与流转；`verified_model_version` 在这套用例里必然显示「未知」，与 `docs/verification.md:391` 的结论一致。顺带记录一个观察：`models/recording.py:134` 的 `attempt_record` 根本不接受可验证版本这个入参，而同样来自上游声明的 `response_model` 是被记录下来的——也就是说这个字段当前**没有任何写入路径**，界面上也无从区分「上游没给」与「给了但不可验证」。这与术语表「不能验证版本则为 null」并不冲突，所以本次只记为观察，未开 Issue；是否要补一条写入路径或把 `response_model` 一并呈现，属产品口径。
- **脱敏/语义导出只验证到下载由本机浏览器发起。** 没有真实外发给接收方，也没有校验外发侧的接收方一致性。
- **未覆盖「上游返回 503/模型不可用」的界面终态。** 替身已提供 `/_stub/mode=unavailable`，但没有对应用例；`UPSTREAM_UNAVAILABLE` 的界面呈现目前只有后端用例覆盖。
- **未覆盖队列积压的界面表现**（超过一条排队的任务如何在历史列表里排序）、多标签页/多窗口并发操作同一任务。
- 本维度**只支持仓库的默认端口**；端口被占用时用例会直接失败而不是换端口，这是刻意选择（避免在前端代理链路上出现第二个真相）。

## 端到端披露面板定位：按摘要文案取代序号（2026-10-13）

任务详情页把「调用账与运行信息」与「查看冻结上下文」渲染成 `details.disclosure`，本维度的两条用例用 `page.locator('details.disclosure summary').first()` 展开前者，依赖的是「它是页面上第一个披露面板」。前端接入两个只读投影（PR #37）后新增的「原始提交」排在它前面，这个前提消失。这一节记录实测到的后果与修法；它是**修正一条既有用例的定位方式**，不新增判定维度，13 条用例的覆盖面不变。

### 披露面板定位：问题与实际检查

- 触发条件：PR #37 之后详情页有三处披露面板，DOM 顺序为「原始提交」→「调用账与运行信息」→「查看冻结上下文」，`.first()` 因此指向「原始提交」。
- 这一点**不会让用例变红**。随后断言取的五个字段（创建时间 / 开始时间 / 结束时间 / 费用 / 排队 / 执行用时）只出现在「调用账与运行信息」的 `dl.facts` 里（「原始提交」的 `dl.facts` 是论断 / DOI / 先前任务 / 冻结配置摘要 / 授权接收方），而 `toHaveText` 与 `not.toHaveText` **不要求元素可见**，在关闭的面板里照样读得到文本。用例由「展开后核对计时字段」退化成「DOM 里存在这些文本」，属于「没报错但不再验证它声明的东西」。
- 实测（临时探针 spec，跑在 PR #37 head `13f707f` 的合并态上，跑完即删）：

  | 观察点 | 实际结果 |
  | --- | --- |
  | 点击 `.first()` 之后打开的面板 | `["原始提交"]`；「调用账与运行信息」仍是 `open=false` |
  | 五个被断言字段的归属 | 全部 `count=1`、`owners=["调用账与运行信息"]`、**`visible=false`** |
  | 该条用例的结论 | **照样通过** |
  | `02` 第 29 行的 `dl.facts` | 不受影响——那一处在 `/#/new` 的授权区（`NewCheck.vue`），属另一个视图 |

### 披露面板定位：修法与变异验证

- 修法：定位由序号换成摘要文案，并在展开后**正面断言面板确已展开**。即 `page.locator('details.disclosure', { hasText: '调用账与运行信息' })` → `.locator('summary').click()` → `expect(...).toHaveAttribute('open', '')`；`facts` 的作用域相应收窄到该面板内的 `dl.facts`。
- 变异测试（判断新断言是否有区分力）：只把点击改回 `page.locator('details.disclosure summary').first().click()`，其余代码一字不动。
- 结果：

  | 检查 | 实际结果 |
  | --- | --- |
  | 修法 + 合并态全量 e2e | **13 passed（1.4m）**（`tests/e2e`，`PAPER_EVIDENCE_E2E_PYTHON` 指向后端 venv） |
  | 变异后只跑 `02` / `04` | **2 failed / 3 passed**；两处失败点均为 `expect(accounting).toHaveAttribute('open', '')`（`02-main-path.spec.ts:65`、`04-upstream-timeout.spec.ts:32`） |
  | 说明 | 新的正面断言确实能识别「点错了面板」；此前的 `toHaveText` 组无论如何都是绿的 |

### 披露面板定位：未覆盖与边界

- 该改动**不依赖 PR #37 合并**：在 `043fe7a`（未含新面板）上，按文案定位同样命中唯一面板，所以先落地既不会与 #37 冲突，也堵住「#37 合并当日 main 上出现绿但失效」的窗口。
- PR #37 新增的「原始提交」与「查看冻结上下文」两个面板**没有端到端覆盖**（该 PR 未改动 `tests/e2e/`），现有覆盖在 `frontend/tests/` 的前端单测。是否补端到端用例属测试范围决定，本次未做。
- 界面没有 `data-testid`，按文案定位与「端到端维度未覆盖与已知限制」里记的成本一致：文案改动要同步改定位。本次没有改变这个前提，只是把它从「靠 DOM 顺序」换成「靠文案」。

## 只读投影前端调用方订正（2026-10-14）

「端到端联调后端缺口：未覆盖」的第一条（`docs/verification.md:541`）原文断言两个只读投影「目前**无前端调用方**：`frontend/src/api/contracts.ts` 已声明两者，但 API 客户端没有对应方法，全仓也搜不到 `evidence-context` 的调用点」。PR #37 把两个投影接进任务详情页并合并为 `add34f8`，该断言随之失效。本节记录订正依据与刻意保留的边界。

### 调用方订正：实际检查

| 检查 | 命令（`origin/main` = `add34f8`） | 结果 |
| --- | --- | --- |
| 契约已声明、客户端已实现 | `git grep -n -e getCheckInput -e getEvidenceContext origin/main -- frontend/src/api/contracts.ts frontend/src/api/http.ts` | `contracts.ts:235` / `:236` 是接口声明，`http.ts:40` / `:41` 分别是 `/input` 与 `/evidence-context` 的实现 |
| 详情页确有调用 | `git grep -n -e loadSubmittedInput -e loadEvidenceContext origin/main -- frontend/src/views/CheckDetail.vue` | `:40`「原始提交」与 `:61`「查看冻结上下文」两个 `details.disclosure` 在 `@toggle` 时按需读取（`:19` / `:20` 取 `work.submittedInput` / `work.evidenceContext`） |
| 该表述在 main 上的残留 | `git grep -n -e 无前端调用方 -e 没有前端调用方 -e "no frontend caller" origin/main` | 只剩 `docs/verification.md:541`（本次订正）与 `:552`（历史记述，见下节） |
| 按行号的交叉引用未被打断 | `git grep -n -e "verification.md:391" origin/main` | 引用共 3 处（本文 `:929`、`:941` 与 `tests/e2e/specs/02-main-path.spec.ts:110`）。本次是**单行替换 + 文末追加**，`:541` **之前**的行号不受影响，`:391` 仍是同一条记录（「没有真实模型调用。……`verified_model_version` 仍只能是 null」）；总行数由 980 增至 1003，追加内容都在 `:541` 之后 |

- 订正只改**调用方**这一半。两个投影「只对本机记录做投影、未接入真实来源或模型」这半句在本次改动后仍然属实，保留原文。
- 同一批表述在 `backend/paper_evidence/api/app.py:272`、`backend/paper_evidence/domain/contracts.py:224`、`docs/architecture.md:288` 与前端注释处已由前端侧在 PR #37 内一并订正；文档侧的这一处按分工留在测试侧，故为本次改动。

### 调用方订正：未覆盖与边界

- **不改写历史记述**：`:552` 属「评审修正（2026-10-12）」小节，记的是当时评审指出的事实，**当时为真**，不改写；`:542` 与 `:543` 同样不动——`:542` 描述 `pmc_fm` 修复前的状态，`:543` 已是 2026-10-12 的时效标注。
- **本次是纯文档订正，不涉及运行行为**：没有代码路径被改动，因此本节不声明任何新的功能验证结果。
- **没有测试对本文档内容作断言**：全仓对 `docs/verification.md` 的引用只有散文式交叉引用（本文自身与 `tests/e2e/specs/02-main-path.spec.ts:110` 的注释）；`tests/tools/test_api_contract.py` 读的是 `docs/architecture.md`。所以本次的验证手段是上表的 grep 与标题唯一性自检，**不是**测试套件。
- **PR #37 引入的两个面板仍无端到端覆盖**（该 PR 未改动 `tests/e2e/`），现有覆盖在 `frontend/tests/` 的前端单测。是否补端到端用例属测试范围决定，本次未做——与「披露面板定位：未覆盖与边界」记的是同一件事，该结论本次不改动。

## 多 worker 不变量落地后的文档订正（2026-10-14）

「性能维度未执行与未覆盖」原先断言 `SqliteStore.claim_next` **不检查是否已有 `RUNNING`**、「一次一个任务」**属于运行约定而非存储层约束**、两个 worker 进程**会各领一条并行执行**。PR #43（合并为 `f051ce0`）把这条改成存储层不变量，三句同时失效。本节记录订正依据；「性能维度覆盖的判定」的「单进程、一次一个任务」一栏也补了落地方式。

### 多 worker 订正：实际检查

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| 领取前先看有没有 `RUNNING` | `git grep -n -A 30 "def claim_next" origin/main -- backend/paper_evidence/storage/sqlite.py` | 同一事务内先 `SELECT 1 FROM tasks WHERE status = 'RUNNING' LIMIT 1`，命中即 `COMMIT` 并返回 `None` |
| 条件 `UPDATE` 的 `rowcount` 已检查 | `git grep -n "rowcount" origin/main -- backend/paper_evidence/storage/sqlite.py` | 不为 1 则 `ROLLBACK` 并返回 `None`；文档字符串写明这是「返回的任务确实被本次调用领取了」的存储层保证 |
| 遗留 `RUNNING` 只在**自己时限已过**时结算 | `git grep -n "deadline_at IS NULL OR deadline_at" origin/main -- backend/paper_evidence/storage/sqlite.py` | 只结算 `deadline_at` 已过、或没有 `deadline_at` 的行，不再无条件结算全部 `RUNNING` |
| 该场景已有用例 | `git ls-tree -r --name-only origin/main -- tests/boundary/` | `test_worker_exclusivity.py`（10 条；本节记这一栏时是 8 条）：另一个进程领不到任务、并发领取恰一个成功、第二个 worker 启动不打断在途任务、自己时限已过的遗留仍结算、结算后队列不永久卡住 |
| 架构文档的表述已同步 | `git grep -n "存储层不变量" origin/main -- docs/architecture.md` | 「**规则**：「同一时刻只执行一个任务」是存储层不变量：只要有任务处于 `RUNNING`，`claim_next` 就拒绝领取」 |

改动形态是**两处单行替换 + 文末追加**：`:856` 与 `:882` 各替换一行、行数不变，因此 `:541` **之前**的行号（含被三处引用的 `:391`）不受影响。

### 多 worker 订正：本机结果

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量 | `pytest -c backend/pyproject.toml -q` | **293 passed, 2 warnings**（146.45s，退出码 0） |
| 前端单测 | `npm --prefix frontend test` | **50 passed / 0 failed** |
| 端到端 | `cd tests/e2e && npm test` | **13 passed**（1.7m） |
| 标题唯一性 | 跳过围栏代码块后统计 `^#{1,6}\s+` | 96 → 100，无重名 |

本机结果只证明本次文档改动没有连带影响，**不作为功能结论**：本次没有改动任何代码路径或用例。

### 多 worker 订正：未覆盖与边界

- **本维度仍未判定该场景**：`tests/performance/` 的 21 条仍按测试方案「保持单进程」的前提跑，判定改由边界维度的 `tests/boundary/test_worker_exclusivity.py` 承担。本节只订正表述，未改动任何用例。
- **没有测试对本文档的内容作断言**：`tests/` 下读 `docs/` 的有两处——`tests/tools/test_api_contract.py` 读 `docs/architecture.md`、`tests/boundary/test_domain_contract.py` 读 `docs/glossary.md`（本节原先是只写了前者，后补上后者；只是补事实清单，当次的手段与结论未变）。本文档 `verification.md` 不在其中，所以本次的验证手段是上表的 grep 与标题唯一性自检，**不是**测试套件。
- **残留窗口仍在，第 3.1 条已由 PR #46 按「订正措辞」处置**：任务的运行时限走单调钟，落库的 `deadline_at` 走墙上钟（「总时限自 RUNNING 起算、不含队列」一栏说的「同源」指两者由同一次领取算出、落库值本身算得对，不是说它们是同一只钟）。阶段边界之外不再比钟，所以任务在 `deadline_at` 过后仍可能合法地处于 `RUNNING`，此时另一个 worker 的结算会先把它记成 `INTERRUPTED`，而原 worker 超时要写的 `TASK_TIMEOUT` 会被条件写入拒绝。窗口本身**没有**消除：能盖住它的小宽限必须大于一次在途的上游尝试（默认 45 秒），而结算判据在存储层拿不到任务侧的超时配置，所以 PR #46（合并为 `958ac17`）只把「可证已死」换成能证明的表述（该行自己的时限已过），并把触发条件与取舍写进 `storage/ports.py`、`docs/development.md`、`docs/architecture.md` 与 `docs/tech-stack.md`。依据见本文「#46 覆盖残留的结论订正」一节。
- **第 3.2 / 3.3 条已由 PR #46 处置，「本 PR 未改」自 #46 起不再成立**：一次性 `drain` 被在途 `RUNNING` 挡住时不再打印「队列已空」，改由 `worker/__main__.py` 的 `closing_message(count, stall)` 报出挡路的那一行（空队列那一句一字未改）；`storage/ports.py` 的 `claim_next` 契约已补第三种来源（条件 `UPDATE` 的 `rowcount` 不为 1），并新增 `running_task()` 供调用方区分「队列为空」与「已有任务在 `RUNNING`」。依据见本文「#46 覆盖残留的结论订正」一节。

## #46 覆盖残留的结论订正（2026-10-14）

PR #46（合并为 `958ac17`）把 Issue #44 后端 / worker 栏的 3.1–3.5 处置完毕：3.1 选「订正措辞」而不是给 `deadline_at` 加宽限期，3.2 让一次性 `drain` 如实报出挡路的 `RUNNING` 行，3.3 给 `storage/ports.py` 的 `claim_next` 补第三种来源。本文因此失效的结论共五处：`:882`（性能维度未覆盖一栏里的「可证已死」与「8 条」）、`:1015` / `:1016`（多 worker 订正的检查表）、`:1036`（残留窗口的处置状态）、`:1037`（`drain` 误报与 `ports` 两种来源）。本节记录订正依据；`:118` / `:169` / `:223` / `:277` 的空队列文案未变，不动。

### 覆盖残留订正：实际检查

| 检查项 | 命令（`origin/main` = `958ac17`） | 结果 |
| --- | --- | --- |
| 结算只认「自己时限已过」 | `git grep -n "deadline_at IS NULL OR deadline_at" origin/main -- backend/paper_evidence/storage/sqlite.py` | 判据仍是 `deadline_at IS NULL OR deadline_at <= _epoch()`，**未加宽限期**；`settle_orphaned_running` 的 docstring 写明「超过时限不等于持有进程已死」 |
| 措辞已换成能证明的表述 | `git grep -n "可证已死" origin/main` | 实现、架构与技术选型文档已无此表述；全仓只剩 `docs/development.md:68` 与 4 处测试注释（`test_worker_exclusivity.py:5` / `:173` / `:225`、`test_storage_lifecycle.py:305`），前者的同族表述不在本次范围内、单独处理 |
| 一次性 `drain` 不再误报队列为空 | `git grep -n "def closing_message" -A 16 origin/main -- backend/paper_evidence/worker/__main__.py` | 空队列返回「worker 本次处理了 N 个任务，队列已空。」（一字未改）；被挡住时改为「worker 本次处理了 N 个任务；有 1 个任务仍在 RUNNING（id，阶段 stage，时限 …），本次未处理。」，且不对队列其余部分下结论 |
| 挡路行在拒绝领取的那一刻读 | `git grep -n -e "running_task" -e "stall" origin/main -- backend/paper_evidence/worker/runner.py` | `SingleTaskWorker.stall` 在 `claim_next` 返回 `None` 的那一刻记录，不是在 `drain` 返回后再读一次 |
| `ports.py` 已补第三种来源 | `git grep -n -A 10 "def claim_next" origin/main -- backend/paper_evidence/storage/ports.py` | docstring 列为三种：队列为空、已有任务 `RUNNING`、条件 `UPDATE` 未移动行；并新增 `running_task()` 契约供调用方区分前两种 |
| 该场景用例数由 8 增到 10 | `grep -c "^def test_" tests/boundary/test_worker_exclusivity.py` | **10** |

### 覆盖残留订正：本机结果

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量 | `pytest -c backend/pyproject.toml -q` | **296 passed, 2 warnings**（66.88s，退出码 0） |
| 前端单测 | `npm --prefix frontend test` | **50 passed / 0 failed** |
| 标题唯一性 | 跳过围栏代码块后统计 `^#{1,6}\s+` | 100 → 104 个标题，无重名 |
| 行尾与行号 | 统计 `\n` 与 `\r\n`；核对被引用的 `:391` / `:541` | 全 CRLF 未混入 LF；总行数由 1037 增至 1068，五处订正均为**不增行数的单行替换**，`:541` **之前**的行号一处未移 |

### 覆盖残留订正：未覆盖与边界

- **本次是纯文档订正，不涉及运行行为**：没有代码路径被改动，本节不声明任何新的功能验证结果。
- **没有测试对本文档的内容作断言**：`tests/` 下读 `docs/` 的有两处——`tests/tools/test_api_contract.py` 读 `docs/architecture.md`、`tests/boundary/test_domain_contract.py` 读 `docs/glossary.md`（本节原先是只写了前者，现补上后者）。本文档 `verification.md` 不在其中，所以本次的验证手段是上表的 grep 与标题唯一性、行尾自检，**不是**测试套件。
- **残留窗口仍在，不等于已修**：3.1 走的是「订正措辞」这条路，`deadline_at` 过后持有者仍可能合法地处于 `RUNNING`、被第二个 worker 抢先记成 `INTERRUPTED`，只是文档与实现不再声称「可证已死」。这条取舍由 Issue #44 记录，本次不重开。
- **`docs/development.md:68` 那处已由 PR #50 订正；剩 4 处测试注释未改**：记这一栏的时候 `:68` 还是待处理，PR #50（`0e9b98f`）随后把同族表述改写为「自己时限已过」，所以此处改为**已处理**；4 处测试注释属可选项，本次未做。

## evidence-context 的 `ordinal` 契约复测（2026-10-14）

本节订正本文「端到端联调后端缺口」一栏里两处随 PR #49（squash-merge `25fc2fd`）过时的结论，
并记录一次**不需要模型密钥**的复测。`AGENTS.md` 把本文档划给测试侧，所以这次改动独立于该功能 PR。

### ordinal 契约复测：订正对象与依据

| 位置 | 原记述 | 现记述 |
| --- | --- | --- |
| `:509` | 证据邻段上下文读取接口「每段带 `entered_context` / `cited` 两个来源标志」 | 补上「与自己的 `ordinal`（冻结来源内的正文序号，从 1 起，与展开邻段用的 `ordinal±1` 是同一个值）」 |
| `:533` | 邻段不是证据「`ContextParagraph` 不带 `validation` 字段」 | 在同一条约束后补上「列表按 `ordinal` 升序，但**列表相邻不等于原文相邻**，判定只能用 `after.ordinal == anchor.ordinal + 1`（Issue #47）」 |

两处都是**单行替换、不增行**，本文总行数不变，`:882` 之后的既有行号一处未移。

### 源层复测：真实冻结来源的序号序列

用产品解析函数（`retrieval/jats.py` 的 `parse_jats`）重新解析库中 `sources.jats_bytes` 的真实全文，
与 `paragraphs` 表逐项比对。**不需要模型密钥，也不需要联网**——冻结全文就在本地库里。

| 来源 | 冻结全文 | 解析段数 | `ordinal` 序列 | 空段占号造成的缺口 | 与库中段落表比对 |
| --- | --- | --- | --- | --- | --- |
| `PMC1182327`（DOI `10.1371/journal.pmed.0020124`），`version_hash` `d8cce55b…` | 74 610 字节 | 32 | `1…32` 连续 | **0 个** | 32 行 `ordinal` **逐项一致** |
| 同一 `pmcid` 的另一次冻结，`version_hash` `574ad062…` | 74 610 字节 | 32 | `1…32` 连续 | **0 个** | 32 行 `ordinal` **逐项一致** |

也就是说：**这份真实来源里没有一个被跳过的空段落**，序号从 1 到 32 一个不落。
「空段落继续占号、段落表因此出现缺口」这条机制在代码里成立（`jats.py` 先 `ordinal += 1`、
后判断文本是否为空），但在本仓库现有的真实来源上**没有实际发生**。

### 投影层复测：真实任务的「列表相邻」差

对库里两条 `COMPLETED` 的真实任务读取 `SqliteStore.evidence_context()`（即 `GET /api/checks/{id}/evidence-context` 的同一个投影），
逐对检查相邻条目：只有当**前一条是锚点**（`cited` 或 `entered_context`）**且**它与下一条的 `ordinal` 差 **大于 1** 时，
「列表相邻」才会与「原文相邻」不一致。

| 任务 | 状态 | 返回段数 | 锚点数 | 列表内相邻对的 `ordinal` 差 | 错位处 |
| --- | --- | --- | --- | --- | --- |
| `5f0649c43fec4c0283833938863363b0` | `COMPLETED` | 30 | 19 | 除 `11→13`、`17→19` 外恒为 1 | **0 处**（两处间隔的前一条都不是锚点，是段落分组之间的自然空档） |
| `bc87b0ce166a4c1ca77e39140df2493c` | `COMPLETED` | 25 | 12 | 除 `17→23`、`25→27`、`29→31` 外恒为 1 | **0 处**（同上） |

**结论：本仓库现有的真实来源没有触发错位。** 两条任务的每个锚点，其 `ordinal±1` 都在返回列表里，
所以「列表相邻」在这份数据上恰好等于「原文相邻」。这与本文在此前记录的口径一致（真实数据未显形），
区别只是：**现在可以用 `ordinal` 直接判定，不必再靠「列表相邻」这个间接推论**。

### ordinal 契约复测：这一节不能被读成什么

- **不是「真实来源已复现该缺陷」**。复测结果是 0 处错位；错位只在**构造样本**上被覆盖：
  `tests/retrieval/test_query_and_jats.py` 验「序号与 `paragraph_id` 尾段一致、被跳过的空段落占号造成段落表缺口」，
  `tests/tools/test_checks_api.py` 构造的正是错位场景——锚点 1 的 `+1` 是空段落、被跳过，列表里紧挨的是另一个锚点 3，
  响应里的序号把它们分开（`1` 与 `3`）。这两处是**人工构造**的样本，不能当作真实来源的实测。
- **「前端尚未修复」只对 #53 合并前的 main 成立**。本节写作时 `frontend/src/state/model.ts` 的 `anchorWindow()` 仍取
  `paragraphs[index ± 1]`、`paragraphRole()` 只按 `cited` / `entered_context` 两枚来源标志拼标签，`git diff 958ac17 origin/main -- frontend/src/state/model.ts` 为**空**；
  这三项都是当时的实测。Issue #20 第 17 项在界面上的错误呈现**已由 PR #53 修复**（`anchorWindow()` 改按 `ordinal±1` 判定），
  所以本节只记录修复前的契约层结论，前端一侧的落地判据与复测见文末「#47 前端侧落地后的结论订正」。
- **不是「该缺陷只在构造数据里存在」**。机制是代码级成立的：任何「锚点的 `+1` 行不存在于段落表」的情形
  （空段落占号造成缺口、锚点是来源末段、`pmc_fm` 回落来源只有 0～1 段）都会让列表里紧挨锚点的条目落到下一个锚点上。
  现场没有触发 ≠ 不能触发。

### 验证手段与限度

- 本节的复测用**产品解析函数**重解析真实 `jats_bytes`、用**同一个只读投影**读取任务，因此验的是产品行为，不是替身；
  全程不调用模型、不联网、不消耗任何预算。临时库是 `.run-r2/data` 的副本，原库与在跑的进程未被触碰。
- **验收基线当时在 main 上仍红（该轮实测，不是推断）**：把 `test/input-context-multianchor-baseline` 那条用例
  临时应用到本分支工作树（只加用例、不碰实现）后跑 `npm --prefix frontend test`，得 **51 条 / 50 passed / 1 failed**，
  失败点即 `an entry counts as the next paragraph only when the server placed it there by ordinal`；跑完已还原，工作区无残留，
  与「`git diff` 为空」互证，排除了「实现已修好只是用例过时」。该结论只对 `d4f8829` 之前的 main 成立，此后见文末订正节。
- `docs/verification.md` 没有测试对其内容作断言（`tests/` 下读 `docs/` 的有两处：`tests/tools/test_api_contract.py` 读
  `docs/architecture.md`、`tests/boundary/test_domain_contract.py` 读 `docs/glossary.md`），所以本次的验证手段是
  脚本断言与 grep，**不是**测试套件。

## #47 前端侧落地后的结论订正（2026-10-15）

PR #53（`fix(frontend): 只有 ordinal±1 才算原文邻段（#47）`，squash-merge `d4f8829`，base `a72f5b00` = #51，head `2b278652`）
把 Issue #20 第 17 项的界面呈现修掉了，Issue #47 随该 PR 自动关闭。`AGENTS.md` 把本文档划给测试侧，
所以这次订正独立于该功能 PR：本节只订正本文随它过时的结论，不重述它的实现，也不改动 `frontend/` 下的代码。

### 订正对象与依据

| 位置 | 原记述 | 现记述 |
| --- | --- | --- |
| `:1119-1122` | 「不是『前端已经正确』……从 #46 合并点到 #49 合并后的 main，该文件一字未改……错误呈现**未被修复**」 | 该判断只对 #53 合并前的 main 成立；`anchorWindow()` 已改按 `ordinal±1` 判定，界面上的错误呈现已修复 |
| `:1131-1134` | 「验收基线在当前 main 上仍红（本轮实测，不是推断）」 | 该结论只对 #53 合并前的 main 成立；那条用例已随 #53 合入，并在合并后的 main 上通过 |

两处都是**段落级替换、不增行**，`:1119` 之前的既有行号一处未移（全仓按行号引用本文档的只有 `:391`（4 处）与 `:541`（2 处），两者都在本节改动之前，
见 `:993` 的自检），新增内容全部在文末：本文总行数由 1138 增至 1184。

### 前端侧的落地判据（在 `d4f8829` 的代码上核对）

| 判据 | 位置 | 内容 |
| --- | --- | --- |
| 邻段按序号判定 | `frontend/src/state/model.ts` 的 `originalNeighbour()` | 新增函数：仅当 `candidate.ordinal === anchor.ordinal + delta` 时返回候选，否则 `null`；`anchorWindow()` 的 `before` / `after` 都由它产出，不再取 `paragraphs[index ± 1]` |
| `ordinal` 成为必填 | `frontend/src/api/validation.ts` 的 `contextParagraph` | 新增校验子：必须是 `Number.isInteger` 且 `>= 1`；缺字段或值为 `0` / `-1` / `1.5` / `'5'` 一律判为契约不合法，`GET /api/checks/{id}/evidence-context` 的响应会被前端拒绝 |
| 用例 | `frontend/tests/input-context.test.mjs` | 我推的恒红基线（`test/input-context-multianchor-baseline` @ `281b0f6`）随 #53 带入；承重断言 `anchorsOnly.after === null` / `anchorsOnly.before === null` 逐字保留，被改写的只有其后的 `paragraphRole(farAnchor)` |

最后一行以用例形式记录：原基线里 `paragraphRole(farAnchor)` 期望写 `'被引用'` 是**错的**（真实值为 `'被引用 · 进入模型上下文'`），
因排在承重断言之后从未执行到，所以 #53 的那处改动是**改正**而非放宽断言。

### 复测（本轮实测，不是推断）

在 `d4f8829`（= 当时的 `origin/main`）新建的工作树上、先 `npm --prefix frontend ci` 装好依赖后跑：

| 命令 | 结果 |
| --- | --- |
| `npm --prefix frontend test` | **52 passed / 0 fail**（`:1131` 记的 51 条 / 50 passed / 1 failed 是 #53 合并前的值） |
| `npm --prefix frontend run build` | `vue-tsc --noEmit` 与 Vite 生产构建均通过 |

### 这一节不能被读成什么

- **不是「真实来源已复现该缺陷」**：上一节「evidence-context 的 `ordinal` 契约复测」的源层与投影层复测结论不变——现有真实来源的 `ordinal` 序列连续，
  两条 `COMPLETED` 任务 0 处错位。本次修的是**机制**（列表相邻 ≠ 原文相邻），在这份数据上不会改变任何界面的可见输出，
  所以这次修复**没有被真实来源的实测覆盖过**。
- **不是「邻段标签也跟着改了」**：`paragraphRole()` 一字未改，仍按 `cited` / `entered_context` 两枚来源标志拼标签；
  变的是「谁算邻段」，不是「邻段怎么标」。
- **不是「本文档有测试兜底了」**：`docs/verification.md` 仍无任何测试对其内容作断言（见上文「验证手段与限度」），
  本节的验证手段是脚本断言、`git` 比对与上表两条命令的实跑输出。

## 测试侧收尾：测试布局守卫与两处过时状态订正（#31，2026-10-15）

本节记录三件事：#31（测试目录的裸 `conftest` 导入）的收尾实测与新增守卫，以及两条随本轮变化而过时的记述。

### #31：根因已由 PR #40 消除，但此前只靠约定

PR #40（squash-merge `043fe7a`）按 #31 的**首选修法**落地：把共享辅助对象从各维度 conftest 移进该维度独有的模块名
（`tests/adversarial/doubles.py`、`tests/functional/acceptance.py`），用例改为显式导入；`tests/performance/` 仍不放 `conftest.py`。

本轮按 #31 的原始复现步骤做前后对照。工作树 `pe-i31`（自 `origin/main` 新建），解释器用主树 `backend/.venv`，
命令 `pytest -c backend/pyproject.toml -q --basetemp=<%TEMP% 下新建目录>`：

| # | 被测提交 | 场景 | 结果 |
| --- | --- | --- | --- |
| A | `a919d5b`（修复前） | 只新增 `tests/performance/conftest.py` | **8 failed / 247 passed** |
| B | `a919d5b` | 同一 `conftest.py`，并在该目录再放一个用例文件 | **8 failed / 248 passed** |
| C | `1d0b3f5`（当前 main） | 与 B 完全相同 | **299 passed / 0 failed** |

A/B 的 8 条失败全部落在 `tests/functional/test_semantic_acceptance.py`——7 个参数的 `test_a_frozen_case_is_judged_against_the_frozen_version`
与 `test_a_sample_that_points_at_a_missing_paragraph_is_refused`——报错为 `ImportError: cannot import name 'VERSION_HASH' from 'conftest' (…/tests/performance/conftest.py)`，
与 #31 的记录逐项一致（条数、失败文件、报错形态）。A 与 B 之差只有一条我加的探针用例，说明**不需要该目录里有用例文件**，只放 `conftest.py` 就足以顶掉排序。
A/B 的总数是 255（再加我那条探针用例），与 #31 记录的「255 基线」**一致**；#31 当时的 276 = 255 + 21 条性能用例，本轮没有把那 21 条一并拉进来，所以 passed 是 247 / 248 而不是 268。可比的是失败条数（8）与失败点，两者逐项吻合。

新增守卫 `tests/boundary/test_test_layout.py`：用 `ast` 扫描 `tests/**/*.py`，断言不存在真实的 `import conftest` 或 `from conftest import …`
（注释与 docstring 里的提及不算，显式相对导入不算）。它另带一条自检用例，检测函数本身失效时守卫会红。
反向核对：临时植入 `tests/boundary/_probe_violation.py`（一行 `from conftest import available_cases`）后守卫立即失败并在消息里指名该文件，移除后恢复通过。

**限度**：守卫只拦「裸名导入」这一条路径。#31 描述的机制本身没有改变——无 `__init__.py` 的目录按 `prepend` 模式导入、
模块名取 `conftest` 时会互相顶掉——只是现在再踩会立刻被用例指出来。`#31` 不涉及模型或浏览器行为，本节也没有这两类验证。

### 两条过时记述的订正

| 位置 | 原记述 | 现记述 |
| --- | --- | --- |
| 本文 `:743` | 「**仍未完成的是真实模型下的语义判断**，需 Issue #7 的「最简模型密钥配置说明」落地后才能补」 | 该缺口只对 2026-10-12 那轮探测成立；真实模型下的判断与证据校验已由 #20 第 2 轮（`deepseek/deepseek-flash`）跑通，仍未完成的只剩论文语义验收 |
| `README.md`「持续集成」段 | 「会运行两个检查：`backend` …、`frontend` …」 | 改为三个检查，补上 `e2e`（Playwright 用例自带前端 dev server 与常驻 worker），本地复现命令同步补 `cd tests/e2e && npm ci && npx playwright install chromium && npm test` |
| `README.md`「当前状态」段 | 「**模型**连通性与论文语义验收尚未验证」 | 拆开写：模型连通性已在真实上游跑通（同上，指向 #20 第 2 轮）；论文语义验收仍未验证，功能样本为人工构造 |

### 一处引用随远端分支删除的说明

`:1131` 与 `:1161` 引用的夹具分支 `test/input-context-multianchor-baseline`（`281b0f6`）**已于 2026-10-15 删除远端分支**。
它唯一改动过的文件 `frontend/tests/input-context.test.mjs` 已随 #53 进入 main，分支上不再有 main 里没有的内容，
保留的只有一条**从未执行到**的错误期望（`paragraphRole(farAnchor) === '被引用'`，真实值为 `'被引用 · 进入模型上下文'`）。
要复现「该断言在修复前会红」不必回到那个分支：把 `model.ts` 的 `originalNeighbour()` 退回按列表相邻取值即可。
同批删除的还有 `docs/verification-ordinal-landed`（`b407d4d`）：它与合并后的 main **逐字节等价**（`git diff origin/main b407d4d` 为空），
且 PR #54 仍持有该提交，删分支不丢内容。

## 真实 PMC 来源契约（2026-10-15）

本节补的是 `tests/tools/test_sources.py` 结构上覆盖不到的一层。那套用例走 `httpx.MockTransport`，钉住的是**本客户端发出的请求形状**，永远钉不住 **PMC 实际返回的形状**。`#28` 正是从这个缝里活下来的：仓库里所有 JATS 夹具都是人工构造的最小快照（`claim_kind: constructed`），而连接器注释曾断言 `pmc_fm` 返回完整 `<body>`，与实测相反——**248 个用例里没有一条能反驳它**。

### 真实 PMC 来源契约：新增内容

- `tests/tools/test_live_source_contract.py`：15 条（5 项 × 3 个 CC BY 记录），**真实网络**。
- `backend/pyproject.toml`：注册 `live` marker；只有 `PAPER_EVIDENCE_LIVE_SOURCES=1` 时才运行。

选取三条已知 CC BY 记录（`PMC1182327` / `PMC8806060` / `PMC7461750`）。**只硬编码公开标识符，仓库内不落存任何文章正文**，每次运行都读当前上游。这是刻意的：既避开版权与体积问题，也让上游格式变更时测试真的会动。

复现命令（需网络出口）：

```bash
PAPER_EVIDENCE_LIVE_SOURCES=1 \
  backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q -m live
```

### 真实 PMC 来源契约：实测

环境：Windows / Python 3.12，2026-10-15。结果是 `15 passed in 11.31s`。同时记录了本次两种 `metadataPrefix` 的元素计数：

| DOI | PMCID | `pmc` body / sec / p（字节） | `pmc_fm` body / sec / p（字节） |
| --- | --- | --- | --- |
| 10.1371/journal.pmed.0020124 | PMC1182327 | **1 / 8 / 38**（74,610） | **0 / 0 / 4**（13,203） |
| 10.1371/journal.pone.0262629 | PMC8806060 | **1 / 20 / 57**（102,152） | **0 / 0 / 3**（13,951） |
| 10.1186/s12889-020-09394-x | PMC7461750 | **1 / 6 / 0**（18,254） | **0 / 0 / 0**（16,688） |

三点与 `#28` 一致，且是**新的一次独立测量**（§「PMC 全文取回：metadataPrefix 修正」那次记的是 2026-10-12）：

1. `pmc` 三例全部含 `<body>`；`pmc_fm` 三例 `<body>` 计数**全为 0**。
2. **`pmc_fm` 并未被拒**——三例都返回 HTTP 200 与题录，没有 `cannotDisseminateFormat`。也就是说**回落分支在这三个记录上根本没被触发**，取到正文靠的是 `pmc` 直接成功。
3. 三个记录的 `license` 均为 `CC BY`、`language` 均为 `en`，`fetch_record` 落到的都是有 `<body>` 的形式。

### 真实 PMC 来源契约：变异验证

断言是否承重，用变异测过，不看"跑绿就算数"：

| 变异 | 结果 |
| --- | --- |
| `_FULL_TEXT_PREFIX` 由 `pmc` 改为 `pmc_fm`（即退回 `#28` 的缺陷行为） | **6 failed, 9 passed** |
| 不设 `PAPER_EVIDENCE_LIVE_SOURCES`（模拟 CI） | **15 skipped, 0 failed** |

失败的 6 条恰是**追踪实现选择**的两项：`test_a_frozen_record_indexes_more_paragraphs_than_its_front_matter`（3 条）与 `test_a_fetched_record_is_english_cc_by_full_text`（3 条）。另外两条纯上游契约用例（`test_the_full_text_prefix_serves_a_body`、`test_the_front_matter_prefix_serves_no_body`）在变异下**保持绿**——这是正确的：它们断言 PMC 在固定字面前缀下返回什么，与实现选了哪个前缀无关。

一条过程记录：这两项的第一版**都用了硬编码前缀**，变异下只有 3 条红。改成「冻结侧走公开的 `fetch_record`、对照侧取 `pmc_fm`」之后才变成 6 条。也就是说，第一版虽然跑绿，却**不追踪实现选择**——同一句"段落数 > 摘要段数"，走不走公开路径，承重能力完全不同。这正好印证 `#28` 的提醒：`quote 存在并不证明 label 正确`。

### 真实 PMC 来源契约：全量基线

| 检查 | 结果 |
| --- | --- |
| 后端全量 `pytest -c backend/pyproject.toml`（不设 `LIVE_SOURCES`） | **300 passed, 15 skipped**，2 warnings（62.69s） |
| `PAPER_EVIDENCE_LIVE_SOURCES=1 -m live` | **15 passed**（11.31s） |
| `npm --prefix frontend test` | **52 passed / 0 failed** |
| `npm --prefix frontend run build` | 通过 |

既有 300 条一条未改、一条未少；新增的 15 条默认进 `skipped` 而**不是失败**，CI（无网络出口）不会因此变红。

### 真实 PMC 来源契约：未覆盖与限度

- **CI 上这 15 条永远 `skipped`**。因此 `300 passed, 15 skipped` **不能读成"来源契约已验证"**——它只说明"来源契约没有被 CI 覆盖"。必须在有网络的环境显式跑，并把结果记进本文件；`skipped` 一律按未验证处理。
- **非 OA 回落路径本轮仍未真实触发**：三个记录的 `pmc` 请求全部成功，`cannotDisseminateFormat` → `pmc_fm` 这条分支一次都没进。该分支**仍只有 mock 覆盖**，与 §「PMC 全文取回：metadataPrefix 修正」记的"没有抽样非 OA 记录的真实响应体"是同一条缺口，本节没有改善它。
- **只有 3 个记录、且都在 OA 子集内**。样本量不足以声称"PMC 的 `pmc_fm` 一律无正文"是普遍规律；它只能证明"这三个记录如此"。要谈普遍性需要抽样协议，本节不提供。
- **只断言结构，不断言语义**：断言是 `<body>` 存在、段落数超过题录+摘要，不比对某段文字。这是刻意的——正文内容会随版本变，结构契约才是连接器的职责边界。
- **上游不可达时这 15 条会以 `UPSTREAM_*` 错误失败**，属环境问题而非缺陷；重跑前先区分，不要记成回归。
- `#28` 的**产品口径仍未定**（非 OA 回落时是否阻断判定）。本节不对该行为置评，也不因为 `pmc` 能取到正文就认为 `#28` 可以关闭。

## 语义报告的可复现性：接入 CI 暴露的一处平台依赖（2026-10-15）

本节与 §「语义验收报告口径」的未覆盖项同源。那一栏写「报告由脚本生成，**尚未在 CI 中启用比对**……接入 CI 只需增加一条命令」。这一条命令接入后**第一次运行就失败了**，而失败原因正是一条此前从未被验证过的假设——`--check` 的"逐字节一致"是**平台相关**的。

### 可复现性：缺陷与证据

`tests/functional/report.py` 的 `sample_fingerprint()` 直接哈希样本文件的**原始字节**：

```python
digest.update(path.read_bytes())
```

样本是 JSON，git 以 **LF** 存储；而 Windows 工作副本经检出转换后是 **CRLF**。于是指纹成了**检出风格**的函数，而不是样本内容的函数。两个字面量始终没有互相校验过，因为**没有任何一处同时见过它们**。

CI 打印的差异只有一行，正是这一处：

```
--- 已提交的报告
+++ 重新生成的结果
@@ -6,3 +6,3 @@
-- 数据来源：`tests/functional/samples/` 的冻结样本，样本集指纹 `sha256:3035a7030a983d95`。
+- 数据来源：`tests/functional/samples/` 的冻结样本，样本集指纹 `sha256:08149557cc65b289`。
```

七个样本文件的原始字节在两个环境里确实不同（本地实测）：

| 形态 | 七个样本文件的 CRLF / 裸 LF | 指纹 |
| --- | --- | --- |
| Windows 工作副本（检出转换后） | 26–29 / 0 | `sha256:3035a7030a983d95` —— **即已提交报告里的那个值** |
| git 存储形态 / Linux 检出 | 0 / 26–29 | `sha256:08149557cc65b289` —— CI runner 上重新生成的值 |

也就是说：**提交进仓库的那份报告，其指纹是在 CRLF 工作副本上算出来的**。报告正文写着「同一样本集重新生成的结果逐字节一致」，而该断言此前**只在生成它的那台机器上成立**。不加这一步 CI，它会一直是绿的——因为唯一的反例需要一个 Linux 环境。

### 可复现性：修复

`sample_fingerprint()` 在哈希前把 CRLF 归一为 LF（`read_bytes().replace(b"\r\n", b"\n")`），使指纹只取决于样本内容。只改一行加一段注释。

报告随之重新生成，指纹由 `sha256:3035a7030a983d95` 变为 **`sha256:08149557cc65b289`**（即 LF 形态的值，与 git 存储形态一致）。报告正文其余部分**逐字未变**——说明指标本身在两个平台上本来就是一致的，唯一漂移的就是指纹。

同一 PR 还让 `--check` 在失败时打印 `difflib` 差异（前 60 行，超出则报剩余行数）。加这一步的直接动机就是本次：只报「不一致」四个字时，定位必须在本地重放或再跑一轮 CI；而差异往往只有一行。

### 可复现性：复测与变异验证

| 检查 | 结果 |
| --- | --- |
| Windows 本地 `python tests/functional/report.py --check`（修复后） | **exit 0**，`逐字节一致（N=7）` |
| CI 的 `backend` 作业 | 见下方「可复现性：未覆盖与限度」——本轮结束时以 CI 结果为准 |
| 变异：把 `contradicted_causality` 的 `expected_label` 由 `相矛盾` 改为 `部分支持` | 指纹由 `08149557cc65b289` → **`bba57c632014be28`**，`--check` **exit 1** |

第三项确认指纹仍然承重：归一化没有把它变成常量。还原样本后 `--check` 回到 exit 0。

### 可复现性：未覆盖与限度

- **归一化只处理 CRLF。** 其它字节差异（编码、BOM、尾随空白、缩进）仍会让指纹改变——这是刻意的，那些属于内容而非检出产物。
- **指纹不覆盖样本内容的正确性。** 它只回答"样本变没变"，不回答"样本对不对"。§「语义验收报告口径」记的 N=7 构造样本、单人标注两条限制**不因本节而改变**。
- **跨平台只在 Windows 与 Linux 上得到验证**，未在 macOS 上验证；「逐字节一致」的适用范围就是这两个平台。
- **本缺陷是由"接入 CI"暴露的，而不是由任何一条用例发现的。** 报告自称可复现已有数日，本地反复通过；只有当第二个环境真的跑了一次，它才现形。这提示一类通病：**"可复现"是双环境性质，单平台通过不构成证据**——与本文件多处记录的"构造样本不足以代表真实来源"是同一类问题，只是这次发生在平台维度而非数据维度。

## 真实模型语义验收：首次实测与产物划分（2026-10-15）

本节记录一件事和一个结论。一件事：**第一次用真实模型驱动验收链路**。结论：**真实模型语义验收目前产不出可用指标，原因不在判断层而在输出契约层**，且这一层**回放式脚本永远看不见**。

### 真实模型语义验收：为什么会有两个产物

`docs/semantic-report.md` 由 `ScriptedGateway` 回放，逐字节可复现，已接 CI 门禁。真实模型跑出的字节**每次都可能不同**，因此**不能**进那一份，也不该被塞进去。所以拆成两份、各司其职：

| 产物 | 谁生成 | 可复现 | CI | 负责证明什么 |
| --- | --- | --- | --- | --- |
| `docs/semantic-report.md` | `tests/functional/report.py` | **逐字节可复现** | **门禁** | 判定链路与分母口径稳定 |
| `docs/semantic-acceptance-live.md` | `tests/functional/live_acceptance.py` | **不可复现** | **不入门禁** | 真实模型下的验收证据 |

新增的 `live_acceptance.py` 通过给 `run_case` 传 `gateway=` 驱动**同一个** `BoundedWorkflow`，不复制第二份实现（`acceptance.py` 的 docstring 明确说明复制会让数字漂移）。密钥只从环境读、不回显；**不接受默认上游**：不设 `PAPER_EVIDENCE_PROVIDER_MODEL` 直接拒绝，因为记录必须写明实际调用的模型。

复现命令（需网络与凭据，会真实计费）：

```bash
PAPER_EVIDENCE_PROVIDER_MODEL=deepseek/deepseek-flash \
PAPER_EVIDENCE_MODEL_API_KEY=... \
  python tests/functional/live_acceptance.py
```

依 `#7` 评论 `6188025713` 的决定：语义验收用 **DeepSeek**（产品默认上游是 `openai/agnes-2.5-flash`，本次实测上游回报的模型是 `deepseek-flash`）。因此本节的所有结论**都带可迁移性限制**，不能直接当作默认上游的表现。

### 真实模型语义验收：实测

环境：Windows / Python 3.12，2026-10-15，`deepseek/deepseek-flash`，样本为 `tests/functional/samples/` 的 **N = 7 人工构造样本**（指纹 `sha256:08149557cc65b289`）。

**同一天、同一模型、同样 7 个样本，跑了三次，三次的结果集都不同：**

| 运行 | 标签与人工核对一致 | 未产出标签 | 失败构成 |
| --- | --- | --- | --- |
| 第 1 次（约 17:00） | 2 / 7 | 5 / 7 | 5 × `MODEL_INVALID_OUTPUT` |
| 第 2 次（19:44） | 1 / 7 | 5 / 7 | 5 × `MODEL_INVALID_OUTPUT` |
| 第 3 次（19:47，即提交的那次） | 2 / 7 | 5 / 7 | 3 × `MODEL_INVALID_OUTPUT` + **2 × `QUOTE_MISMATCH`** |

**连"哪几例能跑完"都在变**：`support_object_scope` 在第 1、3 次通过、第 2 次失败；`contradicted_causality` 第 1、2 次失败、第 3 次产出标签。这不是抖动，而是"每一次运行都是一次独立抽样"。

### 真实模型语义验收：两类失败，都已定位到根因

**一、`MODEL_INVALID_OUTPUT`（主要，3–5 / 7）——已开 `#62`**

`_DECISION_SYSTEM` 只写「decision 含 label、rationale、supported_parts、scope_differences、limitations、evidence」，**从未说明后三个是字符串数组**；模型对单值写成字符串，而 `DecisionDraft` 要求 `list[str]`。更糟的是 `parse_decision_output` 把**所有** `ValidationError` 统一包成 `OutputError("动作字段不合法")`，于是修复提示词拿到的是「上一轮输出不合法：动作字段不合法」——**指向 `action`，实际错在 `decision` 内部**，模型无从修正，白耗唯一一次修复额度。

`contradicted_object` 上抓到的原始输出可直接佐证：模型两次都给出 `"label":"相矛盾"`（与人工核对一致）与逐字引文，却因为 `scope_differences` 是字符串而整单落 `FAILED`。

**二、`QUOTE_MISMATCH`（2 / 7，第 3 次才出现）——不是缺陷，是模型复制 id 不忠实**

第 3 次 `contradicted_causality` 的两次 decision 输出**解析全部通过**、三个字段都是数组、引文也对。逐字符比对确认：引文与该段落文本**完全相同**（`quote_spans` 返回 `[(0, 103)]`）。失败点因此只可能在 `_build_decision` 的第一道检查——当时它报的是「段落未进入本次判断的上下文」，`#82` 之后改为报出候选片段里的 ID（见文末复测）。

对照 `domain/text.py:73` 的规范格式 `p:<source-key>:<version-hash>:<parser>:<ordinal>`：该次模型写的是 `PMC0000001:fff…:1`，**丢了开头两字符 `p:`**，而提示词里展示的是带前缀的完整 id。用同一工作流复跑三次验证：候选 id 确实是 `p:PMC0000001:fff…:1`，模型照着写时通过、丢掉 `p:` 时失败。

**当时读作「模型侧的忠实复制失败、系统的诊断正确、不记为缺陷」；该结论已被推翻**——`#74` 随 `#82` 修复（提示词写明原样照抄方括号内的 ID、诊断改为报出候选里的 ID），修后两轮复测 ID 形状 7/7 正确、`QUOTE_MISMATCH` 归零（见文末）。真正的设计面在提示词：段落 id 是 `p:` + 64 位十六进制 + 版本 + 序号（约 75 字符的不透明串），要求模型逐字复制本身就容易出错。该串约 75 字符且不透明，要求模型逐字复制就必须把这条规则写进提示词。

### 真实模型语义验收：这一节不能被读成什么

- **不是准确率**。三次里各有 5 例**根本没产出标签**，它们既不算对也不算错。「2 / 7」不是准确率，分母里还缺 5 例。
- **不是"模型判断错误"**。主要失败（`MODEL_INVALID_OUTPUT`）发生在结构层，模型的标签在多个被丢弃的输出里与人工核对一致。**不能把 5 / 7 当判断质量。**
- **不覆盖真实来源**。样本仍是**人工构造的最小可解析快照**（每个标注 `claim_kind: "constructed"`），`tests/functional/samples/` 尚未换成真实 PMC 来源集。
- **不覆盖默认上游**。跑的是 DeepSeek，产品默认上游是 Agnes。
- **不是可复现证据**。三次运行三种结果；引用时必须带 `docs/semantic-acceptance-live.md` 顶部的生成时间与模型名。
- **样本量与抽样**：N = 7 且为构造样本，**不足以**对任何总体作估计。

### 真实模型语义验收：状态与后续

- 「真实模型下的语义验收」按 **未覆盖** 记，直到 `#62` 修好并能稳定产出标签。
- 前置依赖：**`#62`**（输出契约，阻塞本项）、**`#61`**（来源层错误路径，阻塞 `#28` 的口径行使）。
- 修好后由测试侧重跑 `live_acceptance.py` 并在 `#62` 回帖；届时的记录仍须注明样本是否已换成真实来源集。
- 一条可复用的教训：**回放式验收脚本对"真实模型输出形状"没有鉴别力**。这是"把上游/模型行为写进 mock 再断言它"的第四次复现（前三次见 `#28` / `#57` / `#61`）。因此真实模型验收**必须固定记录原始输出**——本轮正是靠它把 `MODEL_INVALID_OUTPUT` 定位到 `scope_differences`、把 `QUOTE_MISMATCH` 定位到丢掉的 `p:`，否则只能得到一句无法行动的 `OutputError`。

## 真实来源的证据邻段复测（2026-10-15）

`#20` 清单里有一条：*「原始输入与证据上下文接口（#27）；**证据邻段需在真实来源上复测**（#29 已合并，见 #28）」*。本节执行那次复测。

### 真实来源的证据邻段复测：为什么必须做这一次

邻段展开（`ordinal±1`）此前**在真实来源上恒为空**：非 OA 回落只拿到题录+摘要，冻结点里没有正文，`read_neighbors` 自然什么都展开不出来。`#29` 把取回顺序改成先 `pmc` 之后，这条路径才第一次有内容可展开——但**没有任何真实来源上的验证**，全部证据都来自人工构造的最小快照。

本次新增 `tests/functional/test_live_evidence_context.py`（7 条，带 `live` marker，只有设 `PAPER_EVIDENCE_LIVE_SOURCES=1` 才运行）。

### 真实来源的证据邻段复测：怎么搭的，以及为什么这样搭

| 环节 | 用的是 | 理由 |
| --- | --- | --- |
| 来源 | **真实** `SourceService`（Crossref + PMC），真实抓取、`parse_jats` 真跑 | 要复测的正是"真实正文"这条路径 |
| 冻结与投影 | **真实** `SqliteStore`、`BoundedWorkflow`、`store.evidence_context` | 投影逻辑不做替身 |
| 接口 | **真实入口** `GET /api/checks/{id}/evidence-context`（TestClient） | 清单点的是这个接口，不能只测底层函数 |
| 模型 | **脚本化** `ScriptedGateway` | 要测的是邻段展开，不是模型判断。用真实模型会把 `#62` 的失败混进来，让这次复测测不到目标 |

记录：`PMC1182327` / `10.1371/journal.pmed.0020124`（CC BY）。脚本化判断引用该记录**第 5 段**，引文取自该段真实文本的切片；检索词也取自该段本身——因为「只有进入本次判断上下文的段落才能支撑它」，查询没命中锚点就根本走不到邻段展开。

### 真实来源的证据邻段复测：结果

`PAPER_EVIDENCE_LIVE_SOURCES=1` 下 **7 passed**（6.87s）。断言覆盖：

1. **前提守卫**：真实冻结来源解析出 ≥5 段，且**不全是 `abstract`** —— 这一条正是当初能抓住 `#28` 的检查（回落时冻结点里没有正文）。
2. 脚本化任务 `COMPLETED` 且确实引用了一个真实段落。
3. **展开集合恰等于"各锚点 ordinal±1"**：`evidence_context` 同时展开两个锚点集合（进入上下文的候选 + 判断引用的段落），所以结果是并集、不止三段。逐段比对 `paragraph_id` / `text` / `paragraph_hash` 与真实文档同序号段落一致——**证明是原文相邻，不是列表相邻**。
4. 被引用的锚点带 `cited`，且它同时带 `entered_context`（否则本不该通过逐字校验）。
5. **HTTP 接口与底层投影给出同一集合**（两端不许漂移）。
6. **边界锚点只向内展开**：最后一段只拿到 n-1 与 n，没有凭空造出 n+1。
7. **未知/外来源 id 展开为空**，不跨冻结来源泄漏段落。

**变异验证**（断言是否承重）：

| 变异 | 结果 |
| --- | --- |
| `read_neighbors` 不展开邻段（只返回锚点本身） | **3 failed, 4 passed**——两条邻段断言 + 边界断言转红 |
| 上邻段偏移由 `ordinal + 1` 改为 `ordinal + 2` | **2 failed, 5 passed**——两条"集合相等"断言转红 |
| 不设 `PAPER_EVIDENCE_LIVE_SOURCES`（模拟 CI） | **7 skipped, 0 failed** |

第二项下边界断言**未**转红，这是正确的：最后一段的 `n+1` 与 `n+2` 都越界，查不到任何行，结果不变。

### 真实来源的证据邻段复测：这一节不能被读成什么

- **不是"模型能产出可用证据"**。判断是脚本化的，只提供锚点。模型侧的可信度见 §「真实模型语义验收」——那里最近一轮（2026-10-16 下午）未产出标签 0/7（10-15 的基线才是 5/7）。
- **不覆盖界面**。只到 HTTP 响应体；前端的邻段呈现（`#47` / `#53` 修的「只有 ordinal±1 才算原文邻段」）由前端单测覆盖，不在本次范围内。
- **样本面窄**：一个记录、一个锚点位置。它证明的是"这条链路在真实正文上能展开出原文相邻的段落"，不是"任意记录、任意锚点都正确"。
- **不作为总体估计**，也不覆盖多锚点交叉的情形。
- 与 `PR #57` 同源：仍然是 `live`，**CI 上永久 skip**，`301 passed, 22 skipped` **不能读成"邻段已在 CI 覆盖"**。

### 真实来源的证据邻段复测：一条环境记录

本组用例要真抓上游，会撞上 Crossref / PMC 的**瞬时限流**。`Fetcher` 只做一次**立即**重试，对不带 `Retry-After` 的 429 等于没有退避；实测中出现过一次「上游返回错误状态」（该码只在 429 或 5xx 抛出），随后同一 DOI 直连四个上游均 200。因此取数处加了有界退避重试（4 次、间隔 6s），**失败信号仍然保留**：重试后仍失败会带着上游错误码报出来。这是测试侧对公共接口限流的处理，不是放宽断言。

## 真实来源的冻结清单与一处 `version_hash` 实测（2026-10-15）

本节交付 `#20` 语义验收所需的**来源侧**基础设施，并记录在搭建过程中测出的一处与契约不符的实现行为。

### 真实来源的冻结清单：交付了什么

| 文件 | 作用 |
| --- | --- |
| `tests/functional/freeze_sources.py` | 把真实 PMC 来源取回并冻结成清单；`--check` 重新取回并比对 |
| `tests/functional/sources/*.json` | 三个真实来源的清单（`PMC1182327` / `PMC8806060` / `PMC7461750`，均 CC BY） |
| `tests/functional/test_live_frozen_sources.py` | 5 条 live 用例：形状守卫、许可守卫、逐来源漂移比对 |

**这是"来源侧"的一半**：只做不需要人判断的部分。测试方案要求人工核对 DOI、版本、许可、原文
位置与预期判断——那份人文工作（以及第二人复核）落在清单的 `claims` 字段，脚本**不填**，当前
一律为空数组。

**清单里不提交正文全文**，只提交来源身份、许可、`<article>` 子树哈希、逐段 `ordinal` /
`section` / `paragraph_hash` / 长度 / 首 120 字预览。两个理由：仓库规范要求不将论文全文提交前
先取得明确许可，本 PR 不替团队做这个决定；更重要的是，把快照烘进仓库会让内容漂移**不可见**，
而只存哈希、运行时重取并比对能让漂移立刻显形。需要连正文冻结时可加 `--with-text`，代价是漂移
可见性消失。

### 真实来源的冻结清单：测出的一处 `version_hash` 行为

搭建 `--check` 时它**第一次运行就报三个来源全部漂移**，间隔仅数秒。追查后的实测：

| 项 | 第 1 次取回 | 第 2 次取回（4 秒后） |
| --- | --- | --- |
| OAI 信封 `<responseDate>` | `2026-10-15T12:27:19Z` | `2026-10-15T12:27:23Z` |
| 整包 SHA-256（= `version_hash`） | `497a9d81a8a7b0a9…` | `67c1941d0c637111…` |
| `<article>` 子树 SHA-256 | `caf353df06c98af8…` | `caf353df06c98af8…`（一致） |
| 逐段 `paragraph_hash`、段落数 | 32 段 | 32 段（完全一致） |

`docs/glossary.md` 写的是「`source.version_hash` 为取得的 **JATS 原始字节** SHA-256」，而
`PmcClient.fetch_record` 把 `jats_bytes` 设为**整个 OAI-PMH 响应**（`sources/pmc.py`），
响应里含一个每次请求都不同的 `<responseDate>`。因此：

- **`version_hash` 每次取回都变**，它标识的是"这一次请求"，不是"这个版本"；
- **`source_id = <pmcid>:<version_hash>` 与 `paragraph_id = p:<key>:<version_hash>:…` 也随之
  每次都变**——同一篇文章无法被识别为"同一份"；
- 任何跨次引用段落 id 的东西（诊断记录、`claims`、两次验收之间的对比）都会因此失效。

既有用例全部用固定常量 `VERSION_HASH = "f" * 64`，**没有一条从真实字节算过它**，所以这个语义
从未被检验——与本文件多处记录的"mock 钉不住上游实际返回的形状"是同一类缺口。

**本节的清单因此不把 `paragraph_id` 写进去**（它内嵌那个每变一次的哈希），改用稳定的
`article_sha256` 与逐段 `ordinal` / `paragraph_hash` 作判据；`response_sha256` 与 `version_hash`
仍原样记录，但**不参与比对**，只作"当次取回应用看到什么"的痕迹。是否修实现（例如改为对
`<article>` 子树取哈希）属后端决定，本节只提供证据，不在测试侧改实现。

### 真实来源的冻结清单：结果与变异验证

`--check` 与 5 条 live 用例均通过（`5 passed`，8.94s；`--check` 退出 0，三个来源一致）。变异验证：

| 变异 | 结果 |
| --- | --- |
| 篡改清单里的 `article_sha256` | **1 failed, 4 passed**，报「正文（`<article>`）哈希变了」 |
| 篡改某段的 `paragraph_hash` | **1 failed, 4 passed**，报「ordinal N 的段落正文变了」 |
| 不设 `PAPER_EVIDENCE_LIVE_SOURCES` | **5 skipped, 0 failed** |

### 真实来源的冻结清单：这一节不能被读成什么

- **不是"语义验收已完成"**。这里只有来源侧清单，`claims` 全空；论断、预期标签、引文位置与
  第二人复核都还没做。真实模型侧另有 §「真实模型语义验收」一节，那里最近一轮（2026-10-16 下午）未产出标签 0/7（10-15 的基线才是 5/7）。
- **不是"内容没变过"**，只是"在本次比对时刻与清单一致"。漂移检测只在有人运行它时才生效，
  **CI 上永久 skip**（无网络出口），所以 `301 passed, 20 skipped` **不能读成"来源集已受 CI 保护"**。
- **样本面窄**：三个 CC BY 记录，尚未按四类判断（支持/部分支持/相矛盾/证据不足）与对象、数量、
  条件、因果、否定方向铺开——那是写 `claims` 时的要求，不是本节的结论。
- **`version_hash` 那一条是实测观察，不是缺陷定论**：是否改实现（以及改法）需后端判断；本节只
  记录"契约措辞与实现取哈希的对象不同，且后果是每次取回都变"。
## 提示词与快照修复落地后的复核与真实模型复测（2026-10-16）

### 提示词与快照修复落地后的复核与真实模型复测：这一节记了什么

本轮做三件相互独立的事：复核 `#72` / `#73` / `#75` 三个已合并的 PR；在真实模型上重跑语义验收（两轮）；给验收记录的生成器补三处归因字段。核查基线是 `origin/main = db006613`。三份记录分工不变：本节是**结论**，`docs/semantic-acceptance-live.md` 是**原始输出**，GitHub 上 `#62` / `#74` / `#70` 的回帖是**面向实现方的对照表**。

### 提示词与快照修复落地后的复核与真实模型复测：三个 PR 的复核结论

| PR | 合并提交 | 落地内容 | 测试侧复核 |
| --- | --- | --- | --- |
| `#72` | `b5393adc` | 语义报告标注「回放结果不是系统能力」 | 本轮复跑 `report.py --check` = 逐字节一致（N=7），exit 0 |
| `#73` | `9b28fd50` | 提示词声明三个字段是字符串数组；解析错误按字段定位；提示词版本收敛到 `config.PROMPT_VERSION`（`0.1.0 → 0.2.0`） | 在 PR head 的独立工作树上逐条复核（评审评论）；本轮又在真实模型侧确认其效果，见下一小节 |
| `#75` | `db006613` | `config_snapshot()` 的 `model` 段新增 `provider_model`；`ModelAttempt` 新增 `provider_model` | 本轮记录里「冻结快照里的 `provider_model`」= `deepseek/deepseek-flash`，与常量 `configured_model` = `agnes-2.5-flash` 并排可对账；`#68` 要的那一栏确实有了 |

关于 `docs/semantic-report.md`：`#75` 的实现说明提示「请测试侧补记」。复跑 `report.py --check` 为 exit 0，说明快照改动**没有**进入回放报告的任何一行（该报告不渲染配置快照），因此这个文件**不需要改动**——记在这里，免得下一位读者以为是漏改。

### 提示词与快照修复落地后的复核与真实模型复测：真实模型的两轮结果

在 `db006613` 上用 `deepseek/deepseek-flash` 跑了两轮，样本仍是 `tests/functional/samples/` 的 7 例构造样本（指纹 `sha256:08149557cc65b289`）。

| 项 | 基线 `2026-10-15T19:47:24+08:00` | 轮 A（记录未提交） | 轮 B（记录已提交） |
| --- | --- | --- | --- |
| 标签与人工核对一致 | 2 / 7 | 3 / 7 | **4 / 7** |
| **未产出标签** | **5 / 7** | **2 / 7** | **2 / 7** |
| 其中 `MODEL_INVALID_OUTPUT` | 3 | **0** | **0** |
| 其中 `QUOTE_MISMATCH` | 2 | 2 | 2 |
| 标签由工作流降级产出 | 未统计（当时无此列） | 1 / 7 | 0 / 7 |

`paragraph_id` 的形状分布：

| | 基线 10-15 | 轮 A | 轮 B |
| --- | --- | --- | --- |
| 总数 | 14 | 10 | 9 |
| 带 `p:` 前缀（与提示词一致） | 4 | 5 | 5 |
| **漏 `p:` 前缀** | 9 | 5 | 4 |
| 照抄方括号 | 1 | **0** | **0** |

两条结论：

1. **`#73` 的提示词修复在真实模型上生效**：`MODEL_INVALID_OUTPUT` 由基线 3 例降到两轮都是 0，「照抄方括号」那一类形状同时消失。这是第一次能把该改动的作用从真实模型侧单独读出来——此前只有回放产物，而回放产物对真实模型输出形状没有鉴别力。
2. **剩余的未产出标签全部归到 `#74`**：两轮的 4 个未产出标签**每一个**的错误码都是 `QUOTE_MISMATCH`，成因是 `paragraph_id` 漏 `p:` 前缀（占 ID 总数约一半）。具体挂哪一例会随轮次变化，但「每轮 2 例、恒为 `QUOTE_MISMATCH`」这个形状两轮一致。

### 提示词与快照修复落地后的复核与真实模型复测：另外两条新发现

- **`#78`（新开，高）**：决策提示词只列举了四个标签名，**没有携带判据**（判据在 `docs/glossary.md:23-26` 与 `docs/prd.md:47`，没有一个字进入提示词，可 grep 证实）。术语表把「数量、对象、因果性或范围有重要差异」明确划给「部分支持」，而实测：**两轮合计 14 次最终判定里，标签「部分支持」出现 0 次**；期望「部分支持」且产出标签的 3 次**全部**被判成「相矛盾」，期望「相矛盾」的 3 次则全部判对。即该类别被整个并入了相邻类别。**样本量小（边界相邻 5 例 × 2 轮、单上游），「3 / 3 同向」是观察不是发生率**；与样本量无关的是那一半结构性事实——判据不在提示词里。
- **`#70` 的实例由 2 处增加到 7 处**：今天两轮新增 5 处 `repairs = <case>:decision:1`。这两轮**每个 case 都只有 1 次 `decision`**（没有补读轮），所以这些反向指针 100% 指向不存在的请求，不存在「也许指补读轮」的解释空间。同号 `request_id` 的静默覆盖仍未观察到，维持「潜在风险」的记录。**`#83` 之后口径已变**：新记录一律按被修请求的轮次记 `{case}:decision:0`，修复请求 `request_id` 为 `{task}:output_repair:{该任务内第几次}`；旧记录不追改，断言方向按新口径写。

### 提示词与快照修复落地后的复核与真实模型复测：记录生成器补了三处归因字段

`tests/functional/live_acceptance.py` 生成的记录新增三处，都属于「让数字能说明自己是怎么来的」：

| 新增 | 作用 |
| --- | --- |
| `运行所在提交` | 让一份记录能被指认到具体提交。此前只能靠 PR 描述说明「这是在哪个提交上跑的」 |
| `冻结快照里的 provider_model` | `#68` / `#75` 之后快照里真的有这一栏，记录如实引用，并与 `configured_model` 并排显示 |
| `标签来源` 列（模型判定 / 工作流降级） | 轮 A 的 `insufficient_unrelated` 标签其实是 `graph/workflow.py` 在有界检索为空时自己返回的 `INSUFFICIENT_EVIDENCE`，**不是模型判断**；不区分的话，「一致数」又会把一次降级读成一次能力 |

三处都是**追加**，不改既有字段、不改既有判据。渲染函数做过**不带网络**的冒烟测试（三种来源各一例，含 `commit=None` 的回退分支），断言了「降级计入条数」「两列取值」「`INSUFFICIENT_EVIDENCE` 那段限制文字」都在。

### 提示词与快照修复落地后的复核与真实模型复测：这一节不能被读成什么

- **不是系统准确率**。轮 B 的 4/7 里有 1 例是「期望部分支持、实际相矛盾」（`#78`），另有 2 例连标签都没有。4/7 与 3/7 都不是准确率。
- **不是真实来源集的表现**。两轮都用构造样本（`claim_kind: constructed`），没有换真实来源集，不能外推到真实文献。
- **不是可复现结论**。上游非确定性使同一提交下单个 case 会换位；两轮之间只有「每轮 2 例、恒为 `QUOTE_MISMATCH`」这个形状一致。要下发生率结论需要重复运行，属 `#20` 的重复运行项。
- **不是「`#74` 仍可复现」**。本轮提供的是**修复前基线**；`#82` 已并入 main，修后对照见文末（ID 形状 7/7 正确、`QUOTE_MISMATCH` 归零、未产出标签 0/7）。
- **轮 A 的记录不在仓库里**。它早于「标签来源」列，为保持仓库里只有一份生成产物而没有提交；它的数字写在本节与 `#62` / `#70` / `#74` 的回帖里。仓库内可复核的只有轮 B 的 `docs/semantic-acceptance-live.md`。
- **不是「`#62` 可以关了」**。`#73` 修掉的是它的一半（字段形状），另一半 `paragraph_id` 已拆到 `#74` 并保持 open。
### 提示词与快照修复落地后的真实模型复测（第三轮）：ID 形状归零，未产出标签 0/7

后端 `#82` / `#83` / `#84` 并入 main 后（`bc696c6`），在 `#74` 里已书面同意的付费调用下跑了第三轮
真实模型验收。这一轮回答的是前两轮唯一还悬着的问题：`#74` 修好之后还剩不剩 `QUOTE_MISMATCH`。

**运行环境**：提交 `bc696c6`（`config.PROMPT_VERSION = paper-prompt-0.2.1`）｜上游
`deepseek/deepseek-flash`｜样本 `tests/functional/samples/`，N = 7（构造样本，指纹未变
`sha256:08149557cc65b289`）｜两轮，各 7 例。逐例原始输出在 `docs/semantic-acceptance-live.md`
（只保留最后一轮）。

| 对照点 | 基线 10-15 | 10-16 修复前两轮 | 本轮 A | 本轮 B |
| --- | --- | --- | --- | --- |
| 未产出标签 | 5 / 7 | 2 / 7 | **0 / 7** | **0 / 7** |
| 其中 `QUOTE_MISMATCH` | 2 | 2 | **0** | **0** |
| 其中 `MODEL_INVALID_OUTPUT` | 3 | 0 | 0 | 0 |
| 标签与人工核对一致 | 2 / 7 | 4 / 7 | 5 / 7 | 5 / 7 |
| `paragraph_id` 带 `p:` 前缀 | 4 / 14 | 5 / 9 | **7 / 7** | **7 / 7** |
| 非空 `repairs` | — | — | **0** | **0** |

三条结论：

1. **`#74` 修好了，并且在真实模型上成立。** ID 形状从「约一半漏 `p:`」变成两轮各 **7 / 7 全对**，
   `QUOTE_MISMATCH` 归零，同时**一次修复都没有触发**（两轮 14 次调用 `repairs` 全为空）。这是第一次
   能在真实模型侧把一条缺陷的修复读成「症状消失」，而不是「换了个形状」。
2. **剩余缺口只有一条，且两轮同形。** 5 / 7 里那 2 例仍是 `partial_population_scope` 与
   `partial_quantity`（期望「部分支持」、实际「相矛盾」）——即 `#78`（标签判据不在提示词里）。
   两轮挂的是同一对用例、同一方向，比上一轮「挂哪例会换位」更稳定；但仍是单上游、单样本集、每轮
   7 例，**是观察不是发生率**。
3. **5 / 7 不是准确率。** 其中 `insufficient_unrelated` 在轮 A 由**工作流降级**产出（有界检索为空时
   `graph/workflow.py` 自己返回 `INSUFFICIENT_EVIDENCE`）、轮 B 由**模型判定**产出——同一个正确
   标签，两条不同来路。这正是「标签来源」列存在的理由：不分清就会把一次规则命中读成一次模型能力。

**`#83` 的一处补充观察**：本轮两轮 14 次调用 `repairs` **全部为空**，没有出现新的 `decision:1`
反向指针实例（`#83` 之后即使出现也会按被修请求的轮次记 `{case}:decision:0`）。旧记录里那 7 处
**不追改**：记录的是当时系统写出了什么，改了就不是记录。

**随本轮一并订正的测试侧文件**（均为原位 1 行替换或注释订正，不动 `verification.md` 行数）：

| 位置 | 订正内容 |
| --- | --- |
| `docs/verification.md:1406` | 引用的旧消息「段落未进入本次判断的上下文」已被 `#82` 替换为报出候选片段里的 ID |
| `docs/verification.md:1410` | 「不应记为缺陷」的结论已被 `#74`→`#82` 推翻，改为如实记录这一改判 |
| `docs/verification.md:1473` / `:1546` | 两处「那里 5/7 连标签都没有」是过时状态，改为本轮 0 / 7 |
| `docs/verification.md:1598` | 补 `#83` 的新口径（`{case}:decision:0`） |
| `docs/verification.md:1617` | 「不是 `#74` 已修」改为「不是 `#74` 仍可复现」，指向本文末对照 |
| `tests/functional/freeze_sources.py` | 模块注释两处过时：「`jats_bytes` 存整个 OAI-PMH 响应」「`version_hash` 每次取回都变」；并标注新口径下新冻结清单的 `response_sha256` 会退化成等于 `article_sha256` |
| `tests/functional/acceptance.py` | docstring 原称「every sample records a real PMC source」，与 7 份构造样本实际不符，改为如实声明 |

**同期新增的 live 契约用例**（`tests/tools/test_live_source_contract.py`，落实 `#67` 后端点给测试侧的
那一项）：同一 DOI 走完整 `SourceService.fetch` 两次，断言 `jats_bytes` 逐字节相同、`version_hash` /
`source_id` / 逐段 `ordinal` / 首段 `paragraph_id` 全相同。**实测（2026-10-16，
`10.1371/journal.pmed.0020124`）**：两次都是 73 797 字节、`sha256=caf353df06c98af8…`，断言全过。
它是 `live` marker，CI 无网络出口 → **永久 skip**，`N skipped` 不得读成「已验证」。

### 提示词与快照修复落地后的真实模型复测（第三轮）：这一节不能被读成什么

- **不是准确率**。5 / 7 里有 2 例判错、1 例由规则降级产出；样本是构造样本（`claim_kind: constructed`，
  虚构 DOI 与 `PMC0000001`），且真值**单人标注、无第二人复核**（测试方案「标注」：一人整理、另一人
  复核）。这份数字只能读成「某日某模型某 7 例的一次实测」。
- **不是真实来源集的表现**。两轮都用构造样本；`tests/functional/sources/` 那三个真实来源的
  `claims` **仍是空数组**——「真实来源 + 人核标签」这一半为零，测试方案:49 的**通过条件尚不具备**。
- **不是「语义验收已完成」**。`#74` 修好只解除了「跑不动」这一层；`#78`（判据不在提示词）仍是
  未解决的类别级缺陷。
- **不是可复现结论**。两轮一致只说明「本轮形状稳定」，7 例 × 2 轮不足以支撑发生率。
- **不是默认上游的表现**。本轮上游是 `deepseek/deepseek-flash`（语义验收专用），产品默认上游是
  `openai/agnes-2.5-flash`；换上游须重跑，结论不可直接迁移。
- **不是 CI 保护**。真实模型调用与 live 来源契约检查都不进 CI，CI 也没有网络出口与凭据。
## 未覆盖判据的处置：第一批 4 条（#113，2026-10-22）

### 这一节记了什么

`#111` 附录 B 列了 9 条「`test-plan.md` 有明文判据、仓库没有断言」的缺口。本轮处置其中 4 条：**3 条补上自动化用例，1 条查实是实现缺口而不是测试缺口**。剩下 5 条仍未处置，理由在文末。

### 补了什么

| 判据 | 用例 | 钉住的行为 |
| --- | --- | --- |
| `test-plan.md:83` 上下文不继承 | `tests/session/test_workflow.py::test_a_linked_task_never_sees_the_previous_claim` | 带 `previous_id` 的第二条任务，两次提示词里只有自己的论断；原任务输入不被覆盖，两条历史各自可见 |
| `test-plan.md:106` 预览错误不伪造 BLOCKED | `tests/boundary/test_preview_failure.py`（7 条，5 个错误码参数化） | 上游失败返回错误信封（只有 `error_code` / `message`），任务表与存储都为空；同一条路由在来源正常时返回 200，且同样不建任务 |
| `test-plan.md:91` 重试路径敏感标记 | `tests/adversarial/test_retry_leakage.py`（2 条） | 重试新建的任务在 redacted 包里论断是占位符、标记不出现在响应正文；consented 包保留原句，未授权接收方 400 |

三条都做了**反向对照**，不是只断言「没有坏消息」：

- 隔离用例先断言新论断**在**提示词里。否则「旧论断不在」可能只是因为提示词是空的——那种绿毫无意义。
- 预览用例另加一条成功分支：证明这条路由本来能返回 200，且成功时也不建任务（预览从不入队）。
- 重试用例另加 consented 对照：证明「标记不可见」是脱敏，不是数据丢了。这一条在写的时候真的红过一次——`diagnostic-export` 要求接收方等于运行配置里的观测接收方，否则 400。写进用例后，它同时钉住了「未授权接收方不能导出」。

### 第 1 条：查实是实现缺口，不是测试缺口

`test-plan.md:83` 要求「多主张输入返回拆分提示……作者未澄清时不输出确定判断」。实测三处：

- `backend/paper_evidence/agents/prompts.py` 全文没有「多主张 / 拆分 / 歧义」相关约束（`grep` 无命中），判断提示词只规定四类标签的切分与证据形状；
- 前端 `NewCheck.vue:19` 只有一条静态提示「多个主张请手动拆分，分别提交」——那是输入页的常驻说明，不是对某条输入的响应；
- 因此「多主张 → 只说明歧义、不输出确定判断」这条**运行时行为不存在**，不属于「有实现但没测」。

处置：功能已于 `v0.3.0-test-freeze` 冻结，补提示词属于加功能（还要 bump `PROMPT_VERSION`，并让旧 `config_digest` 快照按设计 409），本轮**不改代码**，如实记为「未实现」。交稿前要不要补，属产品决定，不属测试侧能单方面拍板的事。

### 实测

- 新增用例 **10 条**（隔离 1 + 预览 7 + 重试 2）。三组连同原 `test_workflow.py` 单跑：**47 passed**。
- 全量 `pytest tests`（本工作树先 `npm --prefix frontend ci`）→ **414 passed / 29 skipped**，改前是 404 / 29。
- 各维收集数同步更新在 `test-case-inventory.md`（session 38 / adversarial 31 / boundary 71，七维 423 + 归因 20 = 443）。

### 这一节不能被读成

- **不是 9 条都处置了**。3 条补了、1 条证实未实现、5 条仍待：中文子词召回、中文论断→英文正文、取消 1s/2s 时限、邻段替换不硬判失败、控制失效即停。
- **不是补了用例就等于判据成立**。第 1 条仍不成立——用例补不出一个不存在的实现。
- **不是「9 条都该自动化」**。第 5 条（1 秒响应 / 2 秒收尾）属手工联调，写进 `#20` 执行记录比造一个不稳定计时用例更可信。

## c07 标签改判：由「证据不足」改为「部分支持」（2026-10-22）

### 这一节回答什么

审 `#116` 的指标记录时发现：模型对 `PMC8806060-c07` 判「部分支持」，而原签核是「证据不足」。**改判不是按模型输出改的**——模型答什么都不构成理由，只按 `docs/glossary.md` 的判据重判一次，结论是原签核判错了。

### 判据

- `glossary.md:23`：「部分支持＝支持其中一部分，但**数量、对象、因果性或范围**有重要差异」。c07「DF-Tiny-YOLO 与三个及以上主流检测模型对比时表现更优」：「更优」一半有逐字支撑（第 45 段 `among YOLOv2, Tiny-YOLO, the optimized DF-Tiny-YOLO network offered more advantages than the other two models`，第 39 段 Table 5 给出三项指标）；「三个及以上」这一半不成立（全文横向对比只有 YOLOv2 与 Tiny-YOLO，第 49 段自陈 `difficult to compare with more models`）。差异落在**数量**这一维，正是部分支持列举的情形。
- 同构案例：`PMC13648980-c08`「rPMS 对慢性颈痛患者普遍有效」——「有效」成立、「普遍」不成立，签核为部分支持。c07 是同一结构，两条不能一条判部分支持、一条判证据不足。
- 「证据不足」要求「可核查片段仍不足」。本例片段是有的（第 39/45 段），缺的只是第三个比较对象，故不取该标签。
- 反向检查：若「数量夸大」一律判证据不足，则 `PMC1182327-c05`（85% 的条件性数字被读成一般结论）与 `PMC13648980-c08` 都须跟着改判，整个「部分支持」类会失去意义。

### 改了什么

`tests/functional/sources/PMC8806060.json` 的 c07：`expected_label` 改为「部分支持」；补 `evidence`（第 45 段逐字引文，`ordinal=45`）；重写 `rationale` 与 `limits`；`claim_note` 补记改判理由；**`review` 字段移除**——旧 review 判的是「证据不足」，留着等于对已不成立的结论背书，须按新措辞重签。

改判后 24 条的标签分布：**支持 9 / 部分支持 5 / 相矛盾 6 / 证据不足 4**（改判前是 9 / 4 / 6 / 5）。五种变体的候选数：对象 7 / 数量 10 / 条件 8 / 因果关系 3 / 否定方向 5；四类标签与五种变体仍各有覆盖，`--require-coverage` 不受影响。

### 实测

- `python tests/functional/claims.py` → exit 0；已签核 **23/24**（c07 待重签，未签核不计覆盖），四类标签与五种变体仍全部有覆盖。
- `python tests/functional/claims.py --live` → exit 0；4 个来源「通过」，新引文在第 45 段逐字定位。离线模式会把这条报成「落在预览之外」，只有 `--live` 才验到这一句。
- 全量 `pytest tests` → **404 passed / 29 skipped**，与改签前一致。

### 对 `#116` 的影响（数字要重算，别照抄）

该轮模型输出不变，但金标变了：标签一致 20/24 → **21/24**；macro-F1 0.84 → **0.89**（支持 0.94 / 部分支持 0.80 / 相矛盾 0.92）；部分支持 P/R 0.60/0.75 → **0.80/0.80**；应拒判错误确定判断率 0.40 → **0.25**（R=4，1 例）；真值可判定子集覆盖率 18/19 → **19/20**；可判定覆盖率 83.3% 与摘录定位 34/34 不变。`docs/metrics-live-86.md` 须在重签后重生成，否则其答案集指纹与数字都对不上。

### 这一节不能被读成

- **不是模型的胜利**。依据是术语表与同构案例；模型只是恰好答对，它若答「证据不足」，结论同样是「部分支持」。
- **不是「证据不足」这一类有问题**。另外 4 条证据不足不受影响，覆盖门禁仍覆盖四类。
- **不是门禁已绿**。本分支在重签前 `--require-review` 是红的（23/24），这是刻意的：不放宽门禁换绿。

## 2026-10-22 `#113` 剩余判据补测：中文召回、跨语言正向、邻段负控与指标回归

本节对应 `#113` 的第三、四、六条判据，外加一项不在 `#113` 里、但同属测试侧缺口的
补充：**产出全部头号指标的 `tests/functional/live_metrics.py` 此前零测试**。

### 补了什么

| 判据 | 用例 | 钉住什么 |
| --- | --- | --- |
| `test-plan.md:72` 中文子词召回盲区 | `tests/retrieval/test_chinese_tokenizer.py`（3 条） | 标点切出的整段词元能命中；连续中文里的真子词命中 0 条；中文查询仍被引号包裹，不会变成 MATCH 运算符 |
| `test-plan.md:69`/`:72` 中文论断→英文正文 | `tests/session/test_workflow.py`（2 条） | 中文论断配英文正文可完成并发布标签；把检索词换成中文则命中为空、工作流自返回 `RETRIEVAL_EMPTY` |
| `test-plan.md:47` 邻段负控 | `tests/functional/test_semantic_acceptance.py`（1 条） | 换引同样支持论断的第 2 段仍判通过；同一段引文换成别段原文必须被检出 |
| 指标记录回归 | `tests/functional/test_live_metrics.py`（7 条） | `--from` 重生成与已提交记录**内容一致**；22/24、macro-F1 0.92、44/44、拒判错误率 0.25 独立重算；缺 provider 时在任何网络调用前拒绝 |

### 怎么验的（不是只看绿）

- **中文盲区是「确认限制存在」，不是「期待它被修好」**。`paragraphs_fts` 用
  `tokenize='unicode61'`，汉字属字母类，一段连续中文整体是一个词元，所以「肌筋膜疼痛」
  这类真子词查不到。每条「查不到」都配了「查得到」的正对照，并先断言子串确实逐字
  在正文里，排除「原文根本没这句话」的假阳性。
- **变异检验**：给 `compile_match` 加一道中日韩字符闸门，4 条中文用例变红（唯一没红的
  是那条只用英文查询词的跨语言正例，符合预期）；在工作流入口加一道「论断含中文即拒」，
  两条跨语言用例同时变红。给验收器加「换了段落即失败」，邻段用例变红且只它变红。
  三处变异均已还原，`git status` 只余测试与文档改动。
- **真实模型抽查（用本机 key，1 条，只花 2 次调用）**：`PMC8806060-c01`
  （中文论断「DF-Tiny-YOLO 在四类苹果叶数据集上的 mAP 为 99.99%」）→ 模型首轮产出的
  检索词**全部为英文**（拉丁字母占比 1.00），终态 COMPLETED、标签「支持」、引文定位 3/3。
  这补上了脚本化测试证明不了的一环：跨语言的桥确实在模型侧，不是测试替身假设出来的。
  余额 3.52 → 3.52（CNY，不足 0.01），模型 `deepseek/deepseek-flash`、提示词
  `paper-prompt-0.2.3`。
- **指标回归的三层**：内容相等只说明「和上次渲染的一样」；独立重算（测试自己算
  22/24 与 macro-F1）说明「和这批数据算出来的一样」；第三条断言 `--from` 用的是
  `tests/functional/sources/` 的**当前**金标——`PMC8806060-c07` 在快照里仍是「证据不足」，
  重算后逐条表必须写「部分支持」。缺这一条，「拿旧金标冒充新指标」是查不出来的。

### 实测

| 命令 | 结果 |
| --- | --- |
| `pytest tests`（`main = 12bfe01` + 本批 13 条） | 收集 456，**427 passed / 29 skipped** |
| `pytest tests/functional` | 98 passed / 13 skipped（111） |
| `pytest tests/retrieval` | 15 passed |
| `pytest tests/session` | 40 passed |
| `live_metrics.py --from docs/metrics-live-86.run.json` | exit 0，重生成与已提交记录内容一致（53 355 B，CRLF 归一后逐字节相等） |

### 首轮 CI 红了两次，两处都是「本地能过不等于承重」

**第一次：断言写成本地能过。** 这条回归最初比较**原始字节**，本地全绿、CI 红。不是口径
错，是 `render()` 用 `Path.write_text`：Windows 写 CRLF、Linux 写 LF，「逐字节相等」只在
生成记录的那台机器上成立。改成两侧都把 CRLF 归一成 LF 再比。

**第二次：修完还红，暴露出工具本身有缺陷。** 归一之后内容仍不等，差异只有一行——
`答案集指纹`：仓库里印 `6cfe8482486f9078`（Windows 算的），CI 算出来是
`6b801235496a73e1`。原因是 `live_metrics.source_fingerprint()` 直接哈希
`path.read_bytes()`，而 git 存 LF、Windows 工作区是 CRLF：**同一个答案集在两个平台上
有两个指纹**，也就没法用它核对「这份指标是哪份答案集算出来的」。

这不是测试的问题，是指纹函数的问题，而且 `report.py:366` 的 `sample_fingerprint()`
早就踩过同一个坑并写下了注释（`#67` 的同类：哈希内容，不哈希传输形式）。
`source_fingerprint()` 原样复刻了它。修法与之一致——哈希前归一 CRLF；同时把目录改成
参数，让「换行不影响指纹」可以**直接断言**，而不是等它在另一个平台上才现形。已发布的
记录随之重生成，`答案集指纹` 从 `6cfe848…` 变为 `6b8012…`（只有这一行变化）。

**还有一层值得记**：这条不变性用例的第一版是拿仓库文件当对照组，可 Windows 工作区
本来就是 CRLF，「CRLF 比 CRLF」永远相同——把实现变异回原始字节，它照样绿。改成
**LF 副本 与 CRLF 副本互比**之后才承重（变异后该用例与逐字节用例同时变红）。
一条断言「通过了但没验到东西」，比没有断言更危险。

### 这一节不能被读成

- **不是「中文检索已可用」**。恰恰相反：本节的结论是中文子词召回确实是盲区，且
  跨语言依赖模型把论断译成正文语言的查询词——模型不译（或译错）就退化成拒判。
  这条写进交付物的「已知限制」，不是待修缺陷。
- **不是「指标已经稳定」**。`live_metrics` 的回归测试保护的是**算法与渲染**，
  不保护模型输出：同一答案集两轮之间 `PMC13648980-c04` 一次判「证据不足」、一次判
  「部分支持」，单轮数字仍只能带日期与轮次引用。
- **`#113` 没有全绿**。剩余两条：`:116` 取消时限归 `#20` 手工联调，`:103` 控制失效
  即停仍需能模拟控制失效的替身。

## 2026-10-23 `#121` 合入后的判据收口：在途取消与「控制失效即停」

`#121`（squash 后 `7306c7f`）补齐了 `test-plan.md` 里两条此前只有间接覆盖的判据。
本节只记**测试侧的复核口径与实测**，实现细节见该 PR 与 `docs/defect-analysis.md` 的
D-13 / D-14。

### 覆盖落点

| 判据 | 实现要点 | 用例 | 本节实测 |
| --- | --- | --- | --- |
| `:116` 取消 1 秒内响应、受理后 2 秒内收尾 | `_await_upstream` 在途轮询取消标记（0.2s），受理即中断在途请求；被打断的派发按 `AttemptCancelled` 交回尝试记录，`status="cancelled"`、`usage=null` | `tests/session/test_workflow.py::test_a_cancel_during_an_in_flight_model_call_settles_within_two_seconds`、`::test_a_cancel_during_an_in_flight_source_request_stops_before_the_timeout` | 两条均通过；变异后分别以 5.03 秒失败 |
| `:103` 模拟控制失效须停止后续调用 | `_invoke` 遇零尝试的调用记录即以 `UPSTREAM_UNAVAILABLE` 停机；`_accounting` 改双向判据（记录数 ≥ 派发数，且每条记录都有尝试） | `::test_a_dispatch_the_control_plane_did_not_account_for_stops_the_task`、反例 `::test_missing_usage_alone_does_not_make_the_ledger_incomplete`、`tests/boundary/test_storage_lifecycle.py::test_a_dispatch_that_occupied_quota_without_a_call_record_is_not_verified` | 三条均通过；反例证明「只缺 usage」仍保留结果并记 `unverified` |

### 测试侧做的独立验证

- **全量**：`pytest tests` → 收集 463，**434 passed / 29 skipped**（合入前 427/29）。
- **断言没有被削弱**：`#121` 对测试目录的改动只把 `_call` 辅助并入 `run(..., gateway=None)`
  （为了注入自定义网关），没有删断言、没有放宽阈值。
- **独立变异**（不采信提交信息里自述的「六处」）：删掉 `_await_upstream` 里的
  `cancel_accepted` 轮询后，两条计时用例同时变红，实测 **5.03 秒 > 2 秒预算**——
  与缺陷报告记录的原始现象（替身 4.70 / 4.73 秒）同量级，说明用例锁的是机制而不是结果值。
  变异已还原，`git status` 只余文档改动。

### 这条边界的说明（重要）

`:116` 的自动化用例跑在**脚本化替身 + 虚拟时钟**上，它证明的是「不再等这次调用超时」，
**不证明**真机上从点击取消到 worker 释放确实在 2 秒内。后者需要真实后端 + 常驻 worker +
真实模型，记在 `#20` 的执行记录里（`#20` 正文已单列该行）。两者不能互相替代：
替身跑出的秒数只能算机制证据（实现方在 D-13 里记的是 0.09~0.14 秒，**本节没有复测这个数值**），墙钟才是 `:116` 的验收证据。

`:103` 的「零尝试即停」是确定性分支，替身足够；但「真实上游不回报派发」这一情形
尚未在真环境里复现过——它需要控制面真的丢一次记录，不是靠构造。

### 这一节不能被读成

- **不是「取消已经全部验证」**：墙钟未测，`#20` 那一行仍欠。
- **不是「上游不可用已被覆盖」**：只覆盖了「控制面不回账」这一种失效形态，
  真正的网络失败路径由既有的 `UPSTREAM_UNAVAILABLE` 用例覆盖，两者不重复。
- **不是「换段/换状态都放过」**：`cancelled` 是把状态记准（不是 success、不是 0），
  而 `:103` 是让账不完整时**停下来**——一个放宽方向、一个收紧方向，别读反。

