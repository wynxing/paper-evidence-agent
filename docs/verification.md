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
| 状态 | 在 `codex/project-scaffold` 上处理 PR #4 评审；父提交 `c588193`。本记录随修正提交 `47d15191226d0c394598dec7548433fbc0400bc2` 落地 |
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

来源解析、持久化、真实模型调用、任务执行和论文语义验收仍未实现。实现方没有在 Windows 上重跑测试；原 Windows 失败来自评审记录的 `socket.connect` 拦截，本次改为拦截 `create_connection` 与 `getaddrinfo`，并在 Windows 上改用选择器事件循环。[评审方复审](https://github.com/wynxing/paper-evidence-agent/pull/4#issuecomment-5950892819)报告在 Windows / Python 3.13 上复现此提交为 21 passed、1 warning；这是第三方记录，不是实现方本机验证，也不代表 editable 安装支持 Python 3.13。临时目录为空不能证明没有绝对路径写入。没有性能、取消时限或真实论文验收数据。

## 最新复审修正（2026-10-02）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `51b2a25929daadf9219fe2bd215dc6bee9e0ba0b`；先提交代码及契约文档，再在独立记录提交中写入本节，避免提交哈希自指 |
| 关联 | PR #4 最新复审 N1–N6；在独立工作树、临时分支 `codex/pr4-review-followup` 修复，普通推送回原分支 `codex/project-scaffold` |
| 环境 | Linux、Python 3.12.14、Node.js v26.10.0、npm 12.2.0；新建 venv 并安装既有锁定依赖。没有新增依赖或 CI |
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

业务路由仍为 501，健康检查仍为 200。未实现或验证真实来源请求、任务持久化、模型接入、业务取消/超时执行、性能、论文语义或诊断脱敏能力。对象形状检查不等于完整 TypeScript/OpenAPI 类型等价证明。此新提交未在 Windows 上重跑；上一轮评审方的 21 passed 不能代替本轮 Windows 验证。仓库没有 CI，仍需未参与实现的团队成员独立复审后再考虑合并。

## 后端实现验证记录（2026-10-08）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `7d1c04d24cdfd33ef17347c94f061ac59df8bc1f`；本记录在独立提交中写入，避免提交哈希自指 |
| 关联 | 分支 `feat/backend-implementation`；按 [AGENTS.md](../AGENTS.md) 从更新的 `origin/main` 新建工作树 `.worktrees/backend-impl`，未在主工作区修改 |
| 环境 | Windows / Git Bash、Python 3.12.14、Node.js v22.22.2、npm 10.9.7；新建 venv 安装 `backend/requirements.lock` 与 editable 包；未新增依赖或 CI |
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

未覆盖：真实 Crossref、DOI 官方解析服务、PMC ID 转换与 OAI-PMH、OpenAlex 和本机 LiteLLM Proxy 的连通性与契约；Agnes 或任何真实模型调用；LangGraph 编排（当前为等价的显式状态机 `graph/workflow.py`）；Langfuse 导出；Playwright 端到端；论文语义验收与研究评测。单 worker、一次一任务的并发假设未做压力验证。该提交未在 Linux 上重跑。仓库未配置 CI，仍需未参与实现的团队成员独立复审后再考虑合并。

## PR #8 复审修正（2026-10-08）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `b0ace2963625b7d584edba766bb91d939a21f1d7`；本记录在独立提交中写入，避免提交哈希自指 |
| 关联 | [PR #8 复审](https://github.com/wynxing/paper-evidence-agent/pull/8#pullrequestreview-5455493360)（`2cf33e6` 上 4 项阻塞、3 项建议同 PR 修、8 项非阻塞建议）；分支 `feat/backend-implementation`，仍在工作树 `.worktrees/backend-impl` |
| 环境 | Windows / Git Bash、Python 3.12.14、Node.js v22.22.2、npm 10.9.7；沿用既有 venv 与锁定依赖，未新增依赖或 CI |
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

未覆盖（与上一节相同并新增）：真实 Crossref、DOI 官方解析、PMC ID 转换与 OAI-PMH、OpenAlex、本机 LiteLLM Proxy 仍未实测，连接器与网关只用 `httpx.MockTransport`；论文语义验收与研究评测未执行；LangGraph 编排、Langfuse 导出、Playwright 端到端仍未接入；并发与性能未压测。已知限制：任务在 RUNNING 期间被受理取消后，若结果写入恰好落在工作流最后一次取消检查与终态写入之间，该终态仍会按结果提交（存储层的条件写入只保护已提交的终态）；已受理取消与完成结果之间的优先级需在实现取消先行语义时一并处理，本轮未改动该写入条件。本提交未在 Linux 上重跑。仓库未配置 CI，仍需未参与实现的团队成员独立复审后再考虑合并。
