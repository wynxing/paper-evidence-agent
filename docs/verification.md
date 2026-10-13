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
   > ⚠️ **该结论已于 2026-10-12 被实测推翻（Issue #28）**：`pmc_fm` 返回的 `<article>` **不含 `<body>`**，只有题录+摘要；`pmc` 才返回正文（OA 子集记录，3/3 样例）。详见「PMC 全文取回：metadataPrefix 修正」一节。此处保留原文以说明当时的判断依据。
3. `pmc.py` 调用 `Fetcher.get` 时未传 `follow_redirects=True`；`http.py` 默认 `False`，且 301 小于 400 会被 `Fetcher` 原样返回，随后在 `fetch_record` 的 `status_code != 200` 分支被记为 `UPSTREAM_INVALID_REQUEST`。

### 修复

- `config.py`：默认端点改为 `https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`。
- `pmc.py`：`metadataPrefix` 改为 `pmc_fm`（**已于 2026-10-12 订正为先 `pmc`、仅在 `cannotDisseminateFormat` 时回落 `pmc_fm`，详见「PMC 全文取回：metadataPrefix 修正」一节**）；`fetch_record` 的请求显式传 `follow_redirects=True`。

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

### 实际检查

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

### 未覆盖

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

### 实际检查

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

### 未覆盖

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
| 证据邻段上下文读取接口 | 新增 `GET /api/checks/{id}/evidence-context` → `EvidenceContext`。锚点为「进入模型上下文的候选段落」与「最终判断引用的段落」，各自经 source-scoped 的 `read_neighbors` 按 `ordinal±1` 展开，按段落序号升序返回；每段带 `entered_context` / `cited` 两个来源标志 |
| 原始输入读取接口 | 新增 `GET /api/checks/{id}/input` → `CheckInput`，返回提交时原文以及该任务冻结的 `config_digest` 与 `authorized_recipients`。这是一条**按任务**的直接读取、不依赖历史列表是否已加载；`CheckSummary` 也带 `doi`，故它**不是**取得提交 DOI 的唯一路径（评审修正，见下） |
| #16 第 1 条（worker 遇异常退出） | `run_once` 把工厂构造移入 `try`；`drain_forever` 捕获循环级异常后继续 |
| #16 第 2 条（时间戳一致） | `updated_at` / `finished_at` 由同一处 `_now()` 复用 |
| 最简模型密钥配置说明 | `development.md` / `README.md` 写明最小集与失败行为 |

### 实际检查

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
| 邻段不是证据 | `ContextParagraph` 不带 `validation` 字段 |
| 四条终态路径时间戳 | 完成、排队取消、总超时、遗留 `RUNNING` 结算，均满足 `updated_at == finished_at` |
| worker 循环活下去 | 首轮 `run_once` 抛 `RuntimeError` 后循环仍在领取（`calls > 3`），并记录 `Worker loop iteration failed; continuing` |
| 工厂抛异常落终态 | 已领取任务落 `FAILED`、`error_code is None`、`finished_at` 非空，且不可重复领取 |
| 冻结摘要重提边界 | 有效配置未变时，用 `/input` 的冻结摘要重提被接受（`202`）；配置改变后同一摘要被拒（`409`、`error_code=null`、固定文案「配置已更改，请重新预览并确认」） |

### 未覆盖

- 两个只读投影都只对**本机记录**做投影，未接入真实来源或模型，且目前**无前端调用方**：`frontend/src/api/contracts.ts` 已声明两者，但 API 客户端没有对应方法，全仓也搜不到 `evidence-context` 的调用点。
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

#### 实际检查（第二轮）

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

### 实际检查

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

### 未覆盖

- **来源匹配准确率、证据 Recall@k** 需要独立基准与采样协议，本验收集不产出，报告内列为未覆盖而非填 0。
- **不确定区间**需要采样协议，N=7 不估计。
- 报告只覆盖参赛首版有限验收集，与 [评测口径](evaluation.md) 的正式研究评测（120 对）不是同一层，不互相替代。
- 报告由脚本生成，**尚未在 CI 中启用比对**：此前因正文含随 commit 变化的基线行而无法成立，现已具备条件——报告改为逐字节可复现，`python report.py --check` 在提交的报告与重新生成结果不一致时以非零码退出，接入 CI 只需增加一条命令。本次未改 `.github/workflows/`，故仍属未覆盖；在此之前样本变动而报告未重生成时，需手工运行 `python report.py`。

## PMC 全文取回：metadataPrefix 修正（2026-10-12）

| 项目 | 记录 |
| --- | --- |
| 关联 | Issue #28（本缺陷）；#20 清单中 `evidence-context` 邻段能力的阻塞项 |
| 环境 | Windows、Python 3.12.13（`backend/.venv`，uv 创建）、Node 22.22.2 / npm 10.9.7 |
| 对象 | `backend/paper_evidence/sources/pmc.py`、`tests/tools/test_sources.py` |

### 缺陷与根因

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

### 修复

- `fetch_record` **先请求 `pmc`（正文）**；仅在 PMC 返回 OAI 错误码 **`cannotDisseminateFormat`**（记录不在 OA 子集）时，才回落到 `pmc_fm`。其它 OAI 错误照旧映射 `SOURCE_UNAVAILABLE`，且不做第二次请求。
- 请求与解析拆为 `_get_record()`，错误处理按 `error` 元素的 **`code` 属性**判定，不再按「是否存在 `error` 元素」一刀切。
- 就地订正两处与实测相反的说明：`pmc.py` 的常量注释、原测试的 docstring 与函数名（原名 `test_pmc_oai_request_uses_the_full_text_metadata_prefix` 断言 `pmc_fm`，前提本身是错的）。

### 实际检查

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

### 实际检查

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

- **模型密钥缺失**：环境无 `PAPER_EVIDENCE_MODEL_API_KEY`，SDK 传输回落到 `PAPER_EVIDENCE_MODEL_BASE_URL`（默认 `http://127.0.0.1:4000`）后连接被拒，本次探测在 `query_generation` 止步。链路正确性已由 #20 第 1 轮的本地替身上游证明（主流程跑到 `COMPLETED`）；**仍未完成的是真实模型下的语义判断**，需 Issue #7 的「最简模型密钥配置说明」落地后才能补。替身或构造数据的结果不得用于声称语义验收通过。
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

## 端到端维度：界面主路径（2026-10-13）

`docs/test-plan.md` 第 120 行把界面主路径放在 `tests/e2e/`，用 Playwright 覆盖确认来源、同意整次任务的接收方/数据范围/预算、查看 paper agent 的判断与原文位置，以及澄清重提、取消排队与运行中的任务、显示超时与书目导出预览、删除本地记录。这一节记录该维度的落地方式与实测结果；它是**补齐一个整维度缺失**，不替代其他各维的判定。

### 端到端维度的落地

- 依赖自持：`tests/e2e/package.json` 固定 `@playwright/test` 1.64.0，**不改** `frontend/package.json` / `package-lock.json`，避免把测试依赖塞进产品依赖。引入 Playwright 的归属协调见 Issue #26。
- `playwright.config.ts` 的 `webServer` 一次起四个进程：本机上游替身（8765）→ 真 API（8000）→ 常驻 worker（就绪信标 8001）→ 前端 dev server（5173）。端口是硬约束而不是自由参数：`frontend/vite.config.ts:6` 把 `/api`、`/health` 固定代理到 8000，前端 dev server 固定 5173。`reuseExistingServer` 刻意关掉——复用可能是使用者自己的真实后端，那会让用例打到真实上游，而避免这一点正是本维度的目的。
- 上游全部换成替身（`tests/e2e/support/upstreams.py`，stdlib `ThreadingHTTPServer`）：Crossref 元数据与 agency、DOI 解析探针（302）、PMC idconv、PMC OAI-PMH 的 GetRecord（含真 JATS 的 `<article>`）、OpenAlex 线索，外加一个 OpenAI 兼容的 `/v1/chat/completions`。`POST /_stub/delay`、`POST /_stub/mode` 让用例按需制造「任务在途」与「上游不可用」，不必重启进程。
- 两个 Python 进程必须拿到**完全一致**的 `Settings`：提交时 API 用提交的 `config_digest` 与自己的快照比对（`api/app.py:403`），所以来源地址与 `timeouts` 共用一份构造（`support/runtime.py`）。单次模型尝试上限调到 8 秒，只为让「上游超时」用例不必真等 45 秒；两个进程同值，快照仍自洽。
- 任务库的「空」起点由**每轮新建数据目录**保证，不在启动脚本里删上一轮的库：四个 `webServer` 并发启动，worker 可能先一步打开 SQLite，后启动的进程再 `unlink` 就撞上文件锁（实测 `PermissionError: [WinError 32]`）。轨迹与报告同样按轮次分目录，避免 Playwright 启动时去清上一轮的成百个轨迹文件。

### 端到端维度的前置

- Node 侧：`cd tests/e2e && npm ci && npx playwright install chromium`。工作树里还需要 `frontend/node_modules`（前端 dev server 要用），它不在 git 里。
- `PAPER_EVIDENCE_E2E_PYTHON` 指向后端解释器。默认按 `backend/.venv` 找；本机复现时后端 venv 只在主工作树，所以显式指定。
- **不需要模型密钥**：模型网关同样由替身充当，用例不访问网络。这是本维度与 `tests/functional/` 真值判定的分界。
- 运行前 8000 / 5173 / 8765 / 8001 必须空闲。回环地址必须排除在代理之外，理由见下面的过程缺陷第 1 条。
- 本机跑后端全量时要显式给 `--basetemp=<新建目录>`：pytest 收尾清理旧的编号临时目录时会在一次调用里删掉上百个文件，被这台机器的批量删除保护拦下，导致退出码为 1（用例本身全绿）。属于本机环境处置，不改仓库配置。

### 端到端维度实际检查

| 检查 | 实际结果 |
| --- | --- |
| `npx playwright test`（chromium，串行，13 条） | **13 passed（1.6m）**；连续两次运行结果一致，且输出中没有替身侧异常堆栈 |
| 用例分布 | `01-shell` 2 条（空态与真实接口模式、无效链接回落）、`02-main-path` 4 条（提交前必看项、跑完渲染判断与原文位置、刷新读回、运行诊断）、`03-cancel` 1 条（RUNNING 与 QUEUED 两个取消分支）、`04-upstream-timeout` 1 条、`05-diagnostics` 2 条（脱敏包明示书目未遮盖与语义导出单独授权、诊断页深链）、`06-revise-and-delete` 3 条 |
| 本机浏览器 | Playwright 1.64.0 自带的 Chromium（HeadlessChrome 156.0.8078.4）实测可用，**推翻了 Issue #26 里「本机浏览器不可用」的旧结论**（该结论来自 `agent-browser` 返回 empty page 的尝试） |
| 判定对象 | 界面行为与状态流转：状态的可见文案、按钮可用性、路由、渲染出的摘录与段落标识、调用账数字 |
| 两条按设计真等时间的用例 | `03-cancel` 约 21.7s、`04-upstream-timeout` 约 10.9s；其余 11 条各在 0.7–5.4s 之间 |
| 既有的一侧未被破坏 | 后端全量 `pytest -c backend/pyproject.toml -q --basetemp=<新建目录>` → **255 passed，2 warnings**（110.68s，退出码 0）；前端 `npm test` → **41 passed**。本 PR 不动后端与前端代码，这两项只证明新目录没有影响既有用例的收集 |

### 端到端维度的过程缺陷

1. **回环地址被环境代理劫持，四个 `webServer` 一个都起不来（已修）。** 现象是 `Error: Timed out waiting 60000ms from config.webServer`。`DEBUG=pw:webserver` 显示 `127.0.0.1:8000/health` 在进程起来后持续返回 **404**，而同一时刻用 `curl --noproxy` 拿到的却是 `200 {"status":"ok"}`。根因是两条路径都读代理环境变量：Playwright 的就绪检查经 `WebServerPlugin` → `isURLAvailable` → `httpRequest` → `proxy-from-env` 把请求发给 `HTTP_PROXY`（本机为 `http://127.0.0.1:62800`），而该透明代理对回环端口的应答并不等于目标进程的应答；后端用的 `httpx.AsyncClient()`（`api/deps.py:47`）默认 `trust_env=True`，同样会把查来源的请求交给代理。修法是在配置层把回环摘出代理（`NO_PROXY` 管探活 + 四个代理变量置空后传给子进程），并已在配置里写明原因。对照实测：同一请求带代理 404、不带代理 200。
2. **首次运行有三条用例失败，全部是用例自己的问题，不是产品缺陷（已修）。** 记录在此以免被误读成实现缺陷：
   - `02-main-path`「跑完」一条断言 `details.disclosure dl.facts` 里没有「未知」，但详情页的**费用**一栏按口径固定显示「未知」（`CheckDetail.vue:37`，因为调用次数不是费用上限、本机替身也不提供计费）。改为按 `dt` 精确取值，逐个断言创建/开始/结束三个时刻已落定，并把「费用=未知」转成正面断言。
   - `02-main-path`「运行诊断」一条断言尝试行不出现「未知」，但该表第 4 列是**模型版本**，而 `verified_model_version` 在无法验证版本时按口径就是 `null`（`docs/glossary.md:230`、`docs/verification.md:391`），界面显示「未知」是正确行为。改为列级断言：Tokens 列是替身声明的 `33`，模型版本列是「未知」。
   - `06-revise-and-delete`「修改原句」一条漏了「重新读取来源并重新授权」这一步：`workbench.ts` 的 `prepareEdit` 只把 DOI 与原句带进新草稿，`source`/`config` 被清空，`canSubmit` 因此不成立，提交按钮保持禁用。用例补上 `readSource` + `authorize`，并把「草稿里没有来源预览」写成正面断言。
3. **替身按预期吞掉落线，但仍会把断开打成完整 traceback，刷掉用例输出（已修）。** 应用在超时或取消时主动断开上游连接是**被覆盖的行为**（`04-upstream-timeout`、`03-cancel` 正是靠它成立），`BaseHTTPRequestHandler` 却把它当异常记录。替身改为吞掉 `ConnectionError`，并在代码里注明这不是替身故障。

### 端到端维度未覆盖与已知限制

- **界面主路径的判定不构成论文语义结论。** 替身回的是构造数据（固定题名、固定摘录、固定「支持」标签），语义真值仍在 `tests/functional/` 的冻结样本与语义报告口径里。本维度的 13 条不能拿来当准确率或性能数字。
- **没有接进 CI。** `.github/workflows/` 未增加端到端步骤，可见 Issue #26 中待定的「是否接 CI」。CI 跑这套还需要在 runner 上装 Chromium 并接受比后端全量更长的墙钟时间，属团队决定。
- **只覆盖 Chromium，且 headless。** 未覆盖其他浏览器、移动视口与有头模式；界面没有 `data-testid`，定位全靠可见文案与元素 `id`，文案改动会同时改动用例。
- **没有真实模型调用。** 因此「界面显示真实模型的判断」只验证到渲染与流转；`verified_model_version` 在这套用例里必然显示「未知」，与 `docs/verification.md:391` 的结论一致。顺带记录一个观察：`models/recording.py:134` 的 `attempt_record` 根本不接受可验证版本这个入参，而同样来自上游声明的 `response_model` 是被记录下来的——也就是说这个字段当前**没有任何写入路径**，界面上也无从区分「上游没给」与「给了但不可验证」。这与术语表「不能验证版本则为 null」并不冲突，所以本次只记为观察，未开 Issue；是否要补一条写入路径或把 `response_model` 一并呈现，属产品口径。
- **脱敏/语义导出只验证到下载由本机浏览器发起。** 没有真实外发给接收方，也没有校验外发侧的接收方一致性。
- **未覆盖「上游返回 503/模型不可用」的界面终态。** 替身已提供 `/_stub/mode=unavailable`，但没有对应用例；`UPSTREAM_UNAVAILABLE` 的界面呈现目前只有后端用例覆盖。
- **未覆盖队列积压的界面表现**（超过一条排队的任务如何在历史列表里排序）、多标签页/多窗口并发操作同一任务。
- 本维度**只支持仓库的默认端口**；端口被占用时用例会直接失败而不是换端口，这是刻意选择（避免在前端代理链路上出现第二个真相）。
