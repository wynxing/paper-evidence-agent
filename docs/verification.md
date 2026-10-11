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

## 实际检查

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q` | 21 passed，1 条 Starlette TestClient 对 httpx 的弃用警告 |
| `backend/.venv/bin/python -m pip check` | No broken requirements found |
| `npm --prefix frontend ci && npm --prefix frontend run build` | 安装锁定依赖后，vue-tsc 与 Vite 构建通过 |
| README 与开发指南的本地链接、`git diff --check` | 本地链接均存在；`git diff --check` 无输出 |

## 未覆盖项

来源解析、持久化、真实模型调用、任务执行和论文语义验收仍未实现。实现方没有在 Windows 上重跑测试；原 Windows 失败来自评审记录的 `socket.connect` 拦截，本次改为拦截 `create_connection` 与 `getaddrinfo`，并在 Windows 上改用选择器事件循环。[评审方复审](https://github.com/wynxing/paper-evidence-agent/pull/4#issuecomment-5950892819)报告在 Windows / Python 3.13 上复现此提交为 21 passed、1 warning；这是第三方记录，不是实现方本机验证，也不代表 editable 安装支持 Python 3.13。临时目录为空不能证明没有绝对路径写入。没有性能、取消时限或真实论文验收数据。

## 最新复审修正（2026-10-02）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `51b2a25929daadf9219fe2bd215dc6bee9e0ba0b`；先提交代码及契约文档，再在独立记录提交中写入本节，避免提交哈希自指 |
| 关联 | PR #4 最新复审 N1–N6；在独立工作树、临时分支 `codex/pr4-review-followup` 修复，普通推送回原分支 `codex/project-scaffold` |
| 环境 | Linux、Python 3.12.14、Node.js v26.10.0、npm 12.2.0；新建 venv 并安装既有锁定依赖。没有新增依赖 |
| 改动 | 保留 HTTP 错误响应头、来源预览 ContractError 映射、创建任务 409 模型、422 脱敏字段信息、TS 对象形状及响应状态双向检查、默认预算/超时工厂和平台说明 |

### 实际检查

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

### 失败与修复过程

初轮完整测试为 **4 failed / 49 passed**：422 脱敏字段路径使用了当前 FastAPI 已移除的 ModelField.type_，导致已声明的字段也被遮成 `<unknown>`。对照安装版本确认应读取 field_info.annotation 后修复；新增公共响应规则检查后，对象提交的完整套件为上述 54 passed。没有削弱字段路径断言。首次提交因环境未配置 Git 作者身份失败，随后仅在提交命令中沿用原 PR 提交的作者身份，没有修改全局或仓库配置。

### 覆盖与限制

新增检查使用合成请求及测试应用：九种来源预览业务错误保留真实错误码和 HTTP 映射；未定义的错误或其他端点不会被预览映射重分类；405 保留 Allow、自定义头透传、结构化 HTTPException 日志不含原始键值；422 覆盖缺字段、类型错误、非法 JSON、查询字段、数组位置及额外字段脱敏。前后端对象检查覆盖继承、Omit、字段集合、必填性和可空性，包含刻意改变接口的失败用例；响应状态检查覆盖两侧状态增删、错误模型及公共规则移除。七个默认配置值从术语表核对，并验证每次生成独立实例。

业务路由仍为 501，健康检查仍为 200。未实现或验证真实来源请求、任务持久化、模型接入、业务取消/超时执行、性能、论文语义或诊断脱敏能力。对象形状检查不等于完整 TypeScript/OpenAPI 类型等价证明。此新提交未在 Windows 上重跑；上一轮评审方的 21 passed 不能代替本轮 Windows 验证。仓库现有 CI 为 `backend` 与 `frontend`。仍需未参与实现的团队成员独立复审后再考虑合并。

## 后端实现验证记录（2026-10-08）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `7d1c04d24cdfd33ef17347c94f061ac59df8bc1f`；本记录在独立提交中写入，避免提交哈希自指 |
| 关联 | 分支 `feat/backend-implementation`；按 [AGENTS.md](../AGENTS.md) 从更新的 `origin/main` 新建工作树 `.worktrees/backend-impl`，未在主工作区修改 |
| 环境 | Windows / Git Bash、Python 3.12.14、Node.js v22.22.2、npm 10.9.7；新建 venv 安装 `backend/requirements.lock` 与 editable 包；未新增依赖 |
| 对象 | 后端实现：领域摘要与文本契约、SQLite+FTS5 存储、FTS5 检索与 JATS 冻结、来源连接器、模型网关、有界核验状态机、诊断投影、本地轨迹、HTTP 路由与单进程 worker；README 与开发指南同步更新 |

### 实际检查

以下命令均从工作树仓库根目录执行；完整测试与构建在对象提交已落地后运行。

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml -q` | **108 passed，1 warning**。警告仍为 Starlette TestClient 对 httpx 的既有弃用提示，未隐藏 |
| `backend/.venv/Scripts/python.exe -m pip check` | No broken requirements found |
| `npm --prefix frontend ci`、`npm --prefix frontend run build` | 安装锁定依赖成功；vue-tsc 类型检查与 Vite 生产构建通过 |
| `PAPER_EVIDENCE_DATA_DIR=<临时目录> backend/.venv/Scripts/python.exe -m paper_evidence.worker` | 退出码 `0`，输出“本次处理了 0 个任务，队列已空” |
| 本地 Markdown 文件链接检查（README、architecture、development、verification） | 42 个本地文件链接存在；不检查锚点及外部 URL |
| `git diff --cached --check`、暂存文件范围与凭据模式检查 | 无空白错误；代码提交含 37 个任务文件，未包含环境、`node_modules`、`dist` 或缓存；未匹配常见私钥与 token 模式。不是全仓敏感信息审计 |

### 失败与修复过程

实现进行中的一轮为 **4 failed / 104 passed**：两处是实现与契约不一致（DOI 未按大小写不敏感标准化、PMC 记录缺少许可时先于正文语言门槛报错），两处是用例期望写错（负零摘要、引号重复位置）。分别修正 `normalize_doi` 的小写标准化、在来源测试夹具中补上 CC BY 许可声明、并修正用例期望；未削弱任何断言。另修复 `class SqliteStore` 内的 `list` 方法遮蔽内置名导致的注解求值错误（改用 `from __future__ import annotations`）。对象提交最终为本节的 108 passed。

### 覆盖与限制

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

### 实际检查

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

### 失败与修复过程

首轮完整测试为 **11 failed / 97 passed**，其中 9 条是测试替身与期望未随接口同步（`FakeResolver.resolve` 新增 deadline 形参、`ModelFailure` 改为携带 `ModelCall`、`access_url` 期望值），2 条是实现缺陷。新增回归用例又暴露一处复审未提到的既有缺陷：`_decide` 与 `_generate_queries` 的修复路径漏传 `repairs_request_id`，一旦输出结构错误就会抛 `TypeError` 并被记成 `FAILED + error_code=null`；已补齐目标请求 ID 并留下用例。另移除 `sources/http.py` 与 `storage/sqlite.py` 中两处同类断言依赖。未削弱任何断言。

### 覆盖与限制

新增覆盖：确定判断零摘录（修复后发布 / 修复后仍失败为 `QUOTE_MISMATCH`）、「证据不足」可无摘录、修复输出不可解析与请求 3 修复不可解析均为 `MODEL_INVALID_OUTPUT`、仅邻居 retrieve 成功且不消耗修复额度、无 queries 无邻居的 retrieve 被修复、首次空检索拒绝仅邻居 retrieve、引用上下文外段落被修复、摘录错误在修复额度用尽时报 `QUOTE_MISMATCH`、失败与成功路径 `params_digest` 一致、接收方越权 400 与收窄 202、诊断导出只认观测接收方、PMC 转换与 Crossref 的 401/403/400/503 映射、`access_url` 归属、邻居读取与精确读取、墙钟截止时间与到期结算、RUNNING 取消结算、删除的引用计数与单事务。

未覆盖（与上一节相同并新增）：真实 Crossref、DOI 官方解析、PMC ID 转换与 OAI-PMH、OpenAlex、本机 LiteLLM Proxy 仍未实测，连接器与网关只用 `httpx.MockTransport`；论文语义验收与研究评测未执行；LangGraph 编排、Langfuse 导出、Playwright 端到端仍未接入；并发与性能未压测。已知限制：任务在 RUNNING 期间被受理取消后，若结果写入恰好落在工作流最后一次取消检查与终态写入之间，该终态仍会按结果提交（存储层的条件写入只保护已提交的终态）；已受理取消与完成结果之间的优先级需在实现取消先行语义时一并处理，本轮未改动该写入条件。该已知限制已由下一节「取消竞态修正（2026-10-09）」关闭。本提交未在 Linux 上重跑。仓库现有 CI 为 `backend` 与 `frontend`。仍需未参与实现的团队成员独立复审后再考虑合并。

## 取消竞态修正（2026-10-09）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `0f786da840ee243d63a4a4bcc0e29351d08d8d95`；本记录在独立提交中写入，避免提交哈希自指 |
| 关联 | [独立复审复现](https://github.com/wynxing/paper-evidence-agent/pull/8#issuecomment-6062135693)（`283819e0`）与 [复审更新](https://github.com/wynxing/paper-evidence-agent/pull/8#pullrequestreview-5458224438)：上轮被定为「已知限制」的取消竞态改判阻塞，`283819e0` 上的 APPROVE 撤回 |
| 环境 | Windows / Git Bash、Python 3.12.14、Node.js v22.22.2、npm 10.9.7；沿用既有 venv 与锁定依赖，未新增依赖 |
| 对象 | `storage/sqlite.py`、`graph/workflow.py`、`worker/runner.py`、`tests/boundary/test_storage_lifecycle.py`、`tests/session/test_workflow.py`、`docs/development.md` |

### 缺陷与根因

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

### 实际检查

以下命令均从工作树仓库根目录执行。

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml -q --basetemp=<临时目录>` | **142 passed，1 warning**（净增 4 条用例）。警告仍为 Starlette TestClient 对 httpx 的既有弃用提示，未隐藏 |
| `git stash push -- backend/paper_evidence/storage/sqlite.py backend/paper_evidence/graph/workflow.py` 后重跑 4 条新用例 | **3 failed / 1 passed**：取消优先级用例全部失败，护栏用例（无取消时普通完成照常写入）仍通过；随后 `git stash pop` 恢复。确认回归用例可复现该缺陷，不是恒真断言 |
| `backend/.venv/Scripts/python.exe -m pip check` | No broken requirements found |
| `npm --prefix frontend run build` | vue-tsc 类型检查与 Vite 生产构建通过（前端未改动） |
| `PAPER_EVIDENCE_DATA_DIR=<临时目录> backend/.venv/Scripts/python.exe -m paper_evidence.worker` | 退出码 `0`，输出“本次处理了 0 个任务，队列已空” |

### 覆盖与限制

新增覆盖：RUNNING + 已受理取消时 `COMPLETED` 与 `FAILED` 写入均被拒且状态保持 `RUNNING`、随后 `CANCELLED` 落库；无取消时普通完成仍写入（守卫不误伤）；取消在最终 decision 响应返回时受理 → 终态 `CANCELLED` 且 `label`/`decision` 为 `null`；取消先于上游失败受理 → 终态 `CANCELLED` 而非 `FAILED`。

未覆盖（沿用上节）：真实 Crossref、DOI 官方解析、PMC ID 转换与 OAI-PMH、OpenAlex、本机 LiteLLM Proxy 仍未实测，连接器与网关只用 `httpx.MockTransport`；论文语义验收与研究评测未执行；LangGraph 编排、Langfuse 导出、Playwright 端到端仍未接入；并发与性能未压测，单 worker、一次一任务的假设未做压力验证。本提交未在 Linux 上重跑。仓库现有 CI 为 `backend` 与 `frontend`。仍需未参与实现的团队成员独立复审后再考虑合并。

## 前端工作台编排层（2026-10-10）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `af780eb06601ade2ef86dea4ac4ab32e5063a251`；本节在其后的独立提交中写入，避免提交哈希自指 |
| 关联 | PR #5 评审延后的 N4（`useWorkbench` 可注入并补编排测试）与 N5（本记录）；CI 的 `frontend` 作业增加 `npm --prefix frontend test`，作业名仍为 `backend` 与 `frontend` |
| 环境 | Linux、Node.js v22.14.0、npm 10.9.7。命令从仓库根目录执行。未新增依赖，未改锁定文件、后端或公共契约 |
| 对象 | `frontend/src/state/workbench.ts`、`frontend/tests/workbench-orchestration.test.mjs`、`.github/workflows/ci.yml`、README 持续集成两句 |

### 实际检查

`npm ci` 在改代码之前执行，锁定文件与对象提交相同。测试与构建在对象提交落地且工作区干净时执行。差异检查比较的是该提交与 main。

| 检查 | 结果 |
| --- | --- |
| `npm --prefix frontend ci` | 安装 45 个锁定包。安装输出报告 1 个 high severity advisory。未升级依赖 |
| `npm --prefix frontend test` | **32 passed，0 failed**（1 suite）。其中编排层 11 条，原 `frontend/tests/workbench.test.mjs` 21 条。Node 打印 Type Stripping 实验特性警告，未隐藏 |
| `npm --prefix frontend run build` | `vue-tsc --noEmit` 通过，Vite 生产构建通过 |
| `git diff --check origin/main...HEAD` | 无输出，退出码 0。范围是对象提交相对 main，不含本节 |

### 覆盖与限制

编排测试在 Node 内置测试运行器里挂载 `useWorkbench`，注入替身客户端、短间隔的真实轮询器或可控轮询器，以及 hash / 可见性替身。覆盖：提交（含 DOI 规范化、进行中的第二次提交不重发）、轮询推进到终态后停止、网络错误与 503 后续轮询、契约不一致 / 404 / 409 停止轮询、导航后的迟到读取不覆盖当前任务、重试走 `retryCheck` 且新历史行保留 DOI、取消成功后停止轮询、取消失败后续轮询、409 后刷新配置、501 保留草稿且不进入模拟模式、隐藏页面不启动轮询、畸形 hash 提示、注入客户端优先于 demo 模式、未注入时 demo 模式仍用内存客户端、语义导出缺少同意标记时不发请求。

未覆盖：未运行 pytest；未在浏览器中操作工作台；未连接真实后端、文献来源或模型。替身挂载不是 Playwright 端到端。本节不把尚未看到的 CI 结果写成通过。

## 前后端接口缺口（2026-10-11）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `aca988c9423a934e0691e28ed75ed48b9174934f`；本节在其后的独立提交中写入，避免提交哈希自指 |
| 关联 | 前后端接口差异清单（对应 Issue #7）中的 #1、#2、#3、#4、#5、#6、#8、#11；一次契约变更，前后端同批改完 |
| 环境 | Windows、Python 3.12.14、Node.js v22.22.2、npm 10.9.7。后端依赖装在新临时 venv 中，命令从工作树仓库根目录执行。未新增依赖，未改 `pyproject.toml` 依赖列表与锁定文件 |
| 对象 | `backend/paper_evidence/` 下的 `domain/contracts.py`、`domain/text.py`、`storage/sqlite.py`、`sources/service.py`、`config.py`、`api/app.py`、`worker/__main__.py`、`worker/runner.py`；`frontend/src/`；两处契约文档；相关测试 |

### 实际检查

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

### 覆盖

- 契约双向比对：`tests/boundary/test_frontend_shapes.py` 把 `contracts.ts` 与 OpenAPI 逐字段比对（字段名、必填性、可空性、继承与 `Omit`），`tests/tools/test_api_contract.py` 把架构文档的响应状态表与 OpenAPI 双向比对。二者在本轮随契约扩展一起通过，因此新字段的前后端一致是被断言过的，不是只看代码。这 6 条用例在本次之前的工作树里因未安装 Node 与前端依赖而未实际执行。
- 存储：历史行带摘要与创建时间、倒序、筛选；详情返回原句、书目与三个时刻；排队期取消会写 `finished_at`；书目索引保留作者与年份；旧行缺 `authors`/`year` 时按空值读出；用构造的旧版 schema 数据库打开后补齐列且保留原有行。
- 接口：历史与详情返回新字段、按 `status` 筛选；诊断导出对空字符串与全空白收件人返回 `400`，对带首尾空格的已授权收件人按归一化值返回 `200`；配置读取归一化 `"A, B"` 与全空白值。
- 前端：演示数据满足新契约；历史倒序与摘要；详情计时助手在缺失或时间倒挂时返回未知而非估算；未缓存上下文时由任务记录恢复原句，从而「修改原句」「拆分论断」可用，且任务未记录原句时仍拒绝；重试草稿仍不填原句。

### 未覆盖

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

### 缺陷与根因

三项叠加，全部在 PMC 全文取回链路上，mock 测试无法暴露：

1. `config.py` 的默认 `pmc_oai_url` 仍指向 `https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi`，该地址现返回 **301**，重定向到 `https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`。
2. `pmc.py` 的 `fetch_record` 请求 `metadataPrefix=pmc`，但该前缀对多数记录返回 **400 `cannotDisseminateFormat`**；`ListMetadataFormats` 返回可用值为 `oai_dc`、`pmc`、`pmc_fm`，其中**只有 `pmc_fm` 返回含 `<article>` 的完整 JATS 正文**。
3. `pmc.py` 调用 `Fetcher.get` 时未传 `follow_redirects=True`；`http.py` 默认 `False`，且 301 小于 400 会被 `Fetcher` 原样返回，随后在 `fetch_record` 的 `status_code != 200` 分支被记为 `UPSTREAM_INVALID_REQUEST`。

### 修复

- `config.py`：默认端点改为 `https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`。
- `pmc.py`：`metadataPrefix` 改为 `pmc_fm`；`fetch_record` 的请求显式传 `follow_redirects=True`。

### 实际检查

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

### 未覆盖

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

### 实际检查

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

### 覆盖

- 错误映射：十类 litellm 异常到错误码的映射，并单独固定 `Timeout` 不因继承 `APIConnectionError` 而被读成连接失败。穷尽性用例遍历 `litellm.exceptions` 命名空间，要求每个异常类要么被映射、要么在 `NOT_UPSTREAM_FAILURES` 里显式列出，因此 litellm 升版新增异常类会直接失败，而不是静默漏成 `error_code=null`。
- 恢复：可恢复错误消耗一次恢复额度并记 `recovery_kind=retry`；不可恢复错误不重试；`attempts_per_request=1` 时不重试；Retry-After 被等待；Retry-After 超过任务剩余时间时不消耗预算直接失败；任务余量不足时按 `TASK_TIMEOUT` 结束。
- 记账：成功与失败共用同一个 `params_digest`（不是 request id）；每次尝试序号从 1 起；`usage` 与调用标识缺失时为 `null` 而不是 0。
- 线上载荷：发给 SDK 的是配置的 `openai/agnes-2.5-flash` 而不是别名 `paper-default`；`num_retries` 为 0；未配置 `api_base`/`api_key` 时不发送这两个参数。
- 传输选择：默认 `sdk`；未知取值回落默认；端点类别（`provider_default`/`configured_endpoint`/`local_gateway`）与传输方式进入冻结快照并影响 `config_digest`；`api/deps.py` 按配置构造对应实现。
- SDK 入口本身：两条用例经真实 `litellm.acompletion` 加 `mock_response` 走通，证明真实 `ModelResponse` 里确实取得到调用标识与 usage，真实失败也落到同一张映射表。`mock_response` 在派发前返回，不访问网络。
- 依赖闭包：闭包校验覆盖了新增依赖；`_distribution_name` 现能处理 setuptools 旧式 `name (<1,>=x)` 元数据（botocore 仍是这种写法，此前会让 boto 一整支不被遍历），extra 归属修正为依赖自身，litellm 的 `httpx[http2]` 因此被正确遍历。

### 未覆盖

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
