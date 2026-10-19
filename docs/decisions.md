# 决策沿革

本页记录设计归属，不表示应用已实现或 PR 已合并。当前 PR #2 的候选规范为文档 0.6、诊断包 2.2；main 的生效版本仍由合并历史确定，不能仅凭远端存在某个分支认定其生效。

| 决策 | 本 PR 的选择与原因 |
| --- | --- |
| D6 模型入口 | [PR #2](https://github.com/wynxing/paper-evidence-agent/pull/2) 承接并拟替代 [PR #1](https://github.com/wynxing/paper-evidence-agent/pull/1) 的 SDK 直连方案，改为本机 Proxy 集中管理路由及恢复；应用用兼容客户端。[Issue #18](https://github.com/wynxing/paper-evidence-agent/issues/18) 复审后改为以进程内 LiteLLM SDK 为主形态，Proxy 降为可选传输：改变的是 LiteLLM 运行在哪个进程，别名、逐次尝试记账与每请求至多两次上游尝试保持不变；恢复随之从 Proxy 迁到模型适配层，否则换形态后无人承担。跨部署回退仍未实现。 |
| D5 单 Agent 流程 | 单 Agent 不等于单次调用。采用最多三个主请求加一次全局修复；补读只一轮。非法动作可按原修复额度纠正，不能扩大工具或来源权限。 |
| D4 检索 | 首次为空仍需一次有界补充检索；空结果与执行异常分开。FTS5 是首版基线，嵌入检索等待遗漏及消融证据，不作原则性禁用。 |
| D10 首版范围 | 排除项从硬性限制调用能力改为限制核验对象和基础设施：不做全网搜索、自由协商多 Agent 或网关管理后台；不把这些范围限制当作禁止 Proxy、多步或后续嵌入检索的理由。 |
| 授权边界 | 一次授权覆盖任务内数据范围、主/备用接收方和预算；语义诊断与观测外传分别授权。配置改变不能扩大已有任务授权。 |
| 第二轮评审 | [评论](https://github.com/wynxing/paper-evidence-agent/pull/2#issuecomment-5870514101) 中的预算互斥、判据归属、报告对账、具体阻断文案纳入契约；不新增预算终态，不复制其他项目的回放状态机。 |

PR #1 的旧设计保留供追溯，不能混入本 PR 的实现规范。本次不关闭旧 PR、不选择项目许可证、不自动合并；整合后由维护者处理旧 PR 归属。版本快照必须可取回，不能只留哈希。

## 交稿期补充（2026-10-18）

本节记录交稿期（#93）做出的两项范围决定，与上表的历史选择并存：上表写「本次不选择项目许可证」记录的是 PR #1 合并时的处置，已被本节取代。

| 决策 | 选择与原因 |
| --- | --- |
| 许可证 | 采用 **MIT**。仓库根目录新增 `LICENSE`，README 的「许可证」一节指向它。理由：交稿要求包含开源许可证；MIT 最短、最常见，与「本机运行、作者自行部署」的定位一致，不引入专利授权等需要额外说明的条款。版权行写「Paper Evidence Agent contributors」，不写个人真名。 |
| 观测范围 | 交稿与验收**只使用本地轨迹与诊断包**，不接入 Langfuse 出站导出。`tracing/local.py` 只写本地 `ExecutionRecord`；`config_snapshot().observability.langfuse_enabled` 与 `diagnosis/projector.py` 的默认值都是 `false`。理由：出站导出属功能定型之后的新增功能，会改 `config_digest`、观测授权与配置面，且导出失败要单独告警；而诊断包（`execution` + `model_calls`）已经能回答「哪一步观察到什么」。要接 Langfuse 时另开决策，不在本次交稿范围内。 |

## 观测导出接入（2026-10-19）

上节「观测范围」记录的是交稿期（#93）的范围决定：只做本地轨迹，不接 Langfuse。本节取代该行中「不接入 Langfuse 出站导出」的部分；同一节的许可证决定不受影响。

| 决策 | 选择与原因 |
| --- | --- |
| 本地轨迹 | 仍是诊断依据。每条 `ExecutionRecord` 先写 SQLite，再变成一条 span；导出失败只丢 span，不丢记录、不改任务结果、不增加业务重试。 |
| OpenTelemetry | Python SDK 手动埋点：`tracing/otel.py` 建 `TracerProvider` + `BatchSpanProcessor`（队列 512、批量 128、单次导出超时 3 秒）。每个任务一个根 span（`paper-evidence check`），每个阶段一条子 span；trace_id 由 `task_id` 的 SHA-256 派生，同一任务重跑仍落回同一条 trace。 |
| Langfuse | OTLP/HTTP：`<host>/api/public/otel/v1/traces`，`Authorization: Basic base64(public_key:secret_key)`，并带 `x-langfuse-ingestion-version: 4`（不带则实时摄取不生效）。Langfuse 只收 HTTP，不收 gRPC。 |
| 启用条件 | 显式 `PAPER_EVIDENCE_LANGFUSE_ENABLED` + `PAPER_EVIDENCE_LANGFUSE_HOST` + 两把密钥 + 已授权观测接收方，缺一不启用。`observability.langfuse_enabled` 写的是**会不会真的导出**；请求启用但配置不全时打一条 WARNING，本地轨迹照常。 |
| 脱敏 | 属性取白名单 `SPAN_ATTRIBUTES`：task_id、span_id、阶段、工具、状态、错误码、耗时、轮次、request_id、config_digest、profile、模型别名、提示词版本。claim、正文、引文、DOI、提示词、模型输出与密钥都不在词汇表里，所以不会因为「忘了过滤」而外泄。 |
| 配置面 | 端点和密钥名可配，地址与密钥不进快照、摘要或日志。启用会改 `config_digest`（`observability` 本来就在快照里），这是有意的：两次运行的摘要不同，才能说明导出面不同。 |

仍没做的，与它为什么不在本次：

- **模型调用的 token / 成本没有作为 span 属性导出。** `ModelAttempt.usage` 有记账，但它挂在调用账上，不在 `ExecutionRecord` 里；把模型调用变成 Langfuse 的 generation 需要在 `models/recording.py` 另开一个 sink，并先给 usage 定一个跨传输的单一来源。那是独立的改动，不塞进本次。
- **没有接 Langfuse 的 score / dataset API。** 该接口用于把人工复核结果回写为分数；人工答案本身（#86 的 `claims`）还没写完，回写没有对象。
