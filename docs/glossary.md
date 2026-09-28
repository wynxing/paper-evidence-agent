# 术语表

状态：设计稿\
版本：0.4\
日期：2026-09-28\
作者：Wynn\
读者：产品、实现与评测\
相关文档：[产品需求](prd.md)、[架构设计](architecture.md)、[测试方案](test-plan.md)、[技术选型](tech-stack.md)

本文是结果标签、任务状态、阶段、错误码、结果和诊断包字段的唯一登记处。其他文档引用这些定义。

- **规则**：设计稿中已决定的行为，不代表已实现。
- **假设**：需要实验验证的命题。
- **排除**：当前不在范围内的能力。
- **待决**：需要后续证据才能选择的方案。

## 1. 结果标签

界面有六种结果；前五种写入 `label`。「执行失败」只是 `FAILED` 的界面文字，学术标签保持 `null`。

| 展示结果 | 使用条件 | 任务状态 |
| --- | --- | --- |
| 支持 | 指定文献的原文在对应对象、条件和范围下支持论断 | `COMPLETED` |
| 部分支持 | 支持其中一部分，但数量、对象、因果性或范围有重要差异 | `COMPLETED` |
| 相矛盾 | 对应条件下有明确相反证据，不能由没搜到支持证据推导；对应 AGENTS.md 的「反驳」 | `COMPLETED` |
| 证据不足 | 来源可处理且有界检索已完成，但可核查片段仍不足；只能说本次未获得足够证据 | `COMPLETED` |
| 无法核验来源 | 来源身份、可用范围、许可或内容完整性阻断 | `BLOCKED` |
| 执行失败 | 外部请求、模型输出或执行预算导致任务未能完成，不是学术判断 | `FAILED` |

首次检索为空只是中间观察，不直接生成最终标签。外部评审意见不改写任务状态；模型标签不等于客观真值。

## 2. 任务状态

| 状态 | 含义 | 终态 |
| --- | --- | --- |
| `QUEUED` | 已入队 | 否 |
| `RUNNING` | 执行中，包括重试、补读及修复 | 否 |
| `COMPLETED` | 已形成核验结果，包括证据不足 | 是 |
| `BLOCKED` | 来源、许可或完整性阻断 | 是 |
| `FAILED` | 执行失败；`label` 为 `null` | 是 |
| `INTERRUPTED` | 进程启动时发现遗留的 RUNNING；`label` 为 `null` | 是 |

用户重试创建新的 QUEUED 任务并保留原记录；工作流内部恢复不新建任务。只有终态任务可删除或由用户重试。重试须重新确认当前运行配置及云调用范围。

## 3. 阶段

| 阶段标识 | 界面文字 |
| --- | --- |
| `wait` | 等待 |
| `source_identity` | 核对来源 |
| `license` | 检查许可 |
| `fetch` | 获取全文 |
| `query_generation` | 生成检索词 |
| `retrieval` | 检索证据 |
| `decision` | 判断或申请补读 |
| `evidence_validation` | 证据校验 |
| `output_repair` | 修复输出 |

补充检索复用 retrieval 阶段，用轮次区分。网络恢复不增加业务阶段，用尝试序号区分。

## 4. 错误码

下表是任务终态的映射；执行记录也保留已恢复的错误，但不因此把成功任务改为失败。FAILED 的结果字段均为 `null`。

| 错误码 | 条件 | 终态 |
| --- | --- | --- |
| `SOURCE_MISMATCH` | DOI、PMCID 或版本身份冲突，不替换文献 | `BLOCKED` |
| `SOURCE_UNAVAILABLE` | 官方查询确认无首版可用 PMC 全文来源；网络错误不属此类 | `BLOCKED` |
| `LICENSE_UNKNOWN` | 许可缺失或冲突，无法确认 | `BLOCKED` |
| `LICENSE_UNSUPPORTED` | 许可已知但不在首版 CC0/CC BY 支持范围，不代表该许可非法 | `BLOCKED` |
| `CONTENT_INCOMPLETE` | 已取得内容但 JATS 不完整、解析失败，或所需图表无法可靠读取 | `BLOCKED` |
| `RETRIEVAL_EMPTY` | 完成允许的补充检索仍无候选，生成「证据不足」及检索限制 | `COMPLETED` |
| `UPSTREAM_TIMEOUT` | 请求超时，恢复未成功 | `FAILED` |
| `UPSTREAM_RATE_LIMITED` | 上游限流，恢复未成功 | `FAILED` |
| `UPSTREAM_AUTH_FAILED` | 上游或网关认证/授权失败，不重试 | `FAILED` |
| `UPSTREAM_INVALID_REQUEST` | 参数或协议不兼容，不重试 | `FAILED` |
| `UPSTREAM_UNAVAILABLE` | 连接故障或暂时性服务错误，恢复未成功 | `FAILED` |
| `BUDGET_EXCEEDED` | 流程仍要求执行超出授权次数的请求或补读，未形成有效结果 | `FAILED` |
| `MODEL_INVALID_OUTPUT` | 结构或动作不合法，修复机会用尽后仍无效 | `FAILED` |
| `QUOTE_MISMATCH` | 摘录或引用来源校验失败，修复机会用尽后仍无效 | `FAILED` |

恢复后的终态保留最后导致停止的原因，完整错误链保存在 execution 与 attempts。来源 HTTP 响应先由连接器按接口语义解释，不能将所有 404 都当作参数错误。其他未恢复执行错误使用 FAILED 并保留脱敏的异常类别，`error_code` 为 `null`，不强行套用错误含义。

## 5. 证据门槛

「支持」「部分支持」「相矛盾」是确定判断。展示前必须通过来源身份、版本和许可检查，且每条摘录能在保存的同版本段落中逐字定位，结果结构与证据引用有效。模型还须解释对象、条件、数量、因果和否定方向的关系。

确定性校验只能证明引用与结构有效，不能证明语义判断正确；语义质量由 [首版测试](test-plan.md) 和独立标注评估。修复后须重新经过同样的校验，不降低门槛。证据不足可以没有摘录；阻断、失败及中断没有最终 decision。

### 最终判断

API 的 `decision` 与诊断包的 `decision` 使用同一结构，取对象或 `null`。多次模型输出保留在本地任务记录，不作为多个最终结论发布。

| 字段 | 内容 |
| --- | --- |
| `agent` | 固定 `paper` |
| `label` | 四类学术标签之一；来源阻断标签在任务顶层 |
| `rationale` | 判断理由，不是模型内部思维链 |
| `supported_parts` | 支持的论断部分，字符串数组 |
| `scope_differences` | 对象、数量、条件、因果等差异，字符串数组 |
| `limitations` | 覆盖范围及无法判定部分，字符串数组 |
| `evidence[]` | 逐条证据，下表定义 |
| `validation` | 最终结构与证据校验结果，发布的 decision 固定 `pass` |

| 证据字段 | 内容 |
| --- | --- |
| `paragraph_id` | 冻结来源内段落标识 |
| `quote` | 同版本原文逐字摘录 |
| `section` | 原文章节 |
| `source_url` | 原文入口或可用的定位链接 |
| `paragraph_hash` | 段落哈希 |
| `validation` | 该证据定位校验，发布时为 `pass` |

没有稳定 JATS 标识时使用来源版本哈希与段落顺序的本地定位，并在 limitations 标明局限。多个证据各自验证，不用一条真实摘录替其他证据背书。

以下为构造的最终判断形状示例（已脱敏），不代表论文实测或语义验证通过：

```json
{
  "agent": "paper",
  "label": "部分支持",
  "rationale": "<redacted>",
  "supported_parts": [
    "<redacted>"
  ],
  "scope_differences": [
    "<redacted>"
  ],
  "limitations": [
    "<redacted>"
  ],
  "evidence": [
    {
      "paragraph_id": "example-paragraph-1",
      "quote": "<redacted>",
      "section": "<section-1>",
      "source_url": "<source-url>",
      "paragraph_hash": "<hash-1>",
      "validation": "pass"
    },
    {
      "paragraph_id": "example-paragraph-2",
      "quote": "<redacted>",
      "section": "<section-2>",
      "source_url": "<source-url>",
      "paragraph_hash": "<hash-2>",
      "validation": "pass"
    }
  ],
  "validation": "pass"
}
```

## 6. 诊断包

输入诊断包与外部评审返回值分开。输入包不含故障注入真因、正式真值标签或 diagnosis。版本升级为 `2.0`，替代原 `decisions[]` 和单次模型字段；当前没有运行数据，不需要数据库迁移，不承诺 1.0 消费端兼容。

默认 `redacted` 外传包保留结构、标识、状态与用量元数据。论断、查询、摘录、rationale、supported_parts、scope_differences、limitations 等自由文本均使用脱敏占位，不能借解释字段泄漏未发表论断。原始模型响应和密钥永不导出。`consented` 包仅在本地生成，由作者预览并对接收方单独授权后外传；可以包含获许可片段和判断文本，不自动包含完整提示词。无论断原句的包不能用于声称核实语义标签。

### 输入诊断包

| 字段 | 内容 |
| --- | --- |
| `schema_version` | 固定 `2.0` |
| `case_id`, `run_id`, `trace_id` | 任务、运行、轨迹标识 |
| `status`, `label`, `error_code` | 任务状态、结果标签、终止原因；未产生或不适用为 null |
| `input.doi`, `input.claim`, `input.privacy` | DOI、原句或占位、redacted/consented |
| `input.recipient` | 诊断包授权接收方；未授权为 null，与模型接收方分开 |
| `source` | 来源对象；解析未完成时允许 null；内部未知字段也为 null |
| `source.title`, `source.doi`, `source.pmcid`, `source.license`, `source.version` | 已核对的书目、许可和版本，不伪造缺失值 |
| `source.access_url`, `source.retrieved_at`, `source.version_hash` | 获取入口、时间和内容哈希 |
| `run_config.profile`, `run_config.config_digest` | daily/evaluation、脱敏配置快照的摘要 |
| `run_config.authorized_recipients` | 本次允许的模型服务接收方标识，不含密钥 |
| `run_config.limits` | main_requests=3、repair_requests=1、attempts_per_request=2、supplemental_rounds=1 |
| `evidence_candidates[]` | 候选段落记录，字段见下表 |
| `decision` | 上节的最终判断或 null；与尝试记录分开 |
| `execution[]` | 所有已执行步骤，包括失败/阻断前的步骤，字段见下表 |
| `model_calls[]` | 逻辑模型请求与逐次上游尝试，字段见下表 |

| 候选字段 | 内容 |
| --- | --- |
| `paragraph_id`, `section`, `quote`, `paragraph_hash`, `source_url` | 来源定位；quote 服从脱敏模式 |
| `round` | 初始检索 0，补充检索 1 |
| `rank` | 当前轮候选顺序 |
| `entered_context` | 是否进入任一模型请求；具体关联见 model_calls |

| 执行字段 | 内容 |
| --- | --- |
| `stage`, `span_id`, `tool` | 阶段、span、工具名称 |
| `status` | 步骤结果 success/error/blocked，不复用任务状态 |
| `error_code`, `duration_ms` | 原因与耗时，未知为 null |
| `round` | 检索轮次，不适用为 null |
| `request_id` | 关联逻辑模型请求，无模型调用时为 null |

| 模型调用字段 | 内容 |
| --- | --- |
| `request_id`, `purpose`, `round` | 本地逻辑请求 ID；query_generation/decision/output_repair；对应轮次 |
| `model_alias`, `prompt_version`, `params_digest` | 模型别名、提示词版本、脱敏参数摘要 |
| `context_paragraph_ids` | 此次实际进入上下文的段落标识数组 |
| `repairs_request_id` | 输出修复的目标请求 ID，非修复为 null |
| `attempts[]` | 实际发起的上游尝试，下表定义；未发起则为空 |

| 尝试字段 | 内容 |
| --- | --- |
| `attempt_id`, `attempt_index`, `span_id` | 本地唯一标识、从 1 开始的序号、关联 span |
| `gateway_request_id`, `upstream_response_id` | 网关和上游返回标识，拿不到为 null |
| `configured_model`, `deployment_id`, `recipient` | 此次实际路由配置与接收方，来自网关元数据 |
| `response_model`, `verified_model_version` | 上游声称的模型及可验证版本；不能验证版本则为 null，不能用别名代替 |
| `recovery_kind`, `recovery_reason` | none/retry/fallback，以及触发本次恢复的错误码；首次 reason 为 null |
| `status`, `error_code`, `duration_ms` | success/error、错误码和耗时 |
| `usage` | prompt_tokens/completion_tokens/total_tokens 对象；usage 或其缺失子项为 null，不补零 |

调用次数由请求数组及 attempts 数组计算；模型版本和 token 未知不影响正确展示“未知”，但缺失尝试记录不能宣称调用预算或成本已完整核实。网关必须提供逐次元数据，最终响应不能代表所有尝试。原始元数据先脱敏再落日志。

下面是**构造的脱敏超时示例**，不是实测数据；展示一个逻辑请求的两次尝试；为便于阅读，execution 仅列模型阶段，完整导出须同时包含此前的来源检查步骤。成功包的 decision 按上一节定义。

```json
{
  "schema_version": "2.0",
  "case_id": "example-case",
  "run_id": "example-run",
  "trace_id": "example-trace",
  "status": "FAILED",
  "label": null,
  "error_code": "UPSTREAM_TIMEOUT",
  "input": {
    "doi": "<normalized-doi>",
    "claim": "<redacted>",
    "privacy": "redacted",
    "recipient": null
  },
  "source": {
    "title": "<verified-title>",
    "doi": "<normalized-doi>",
    "pmcid": "<pmcid>",
    "license": "CC BY",
    "version": "<version>",
    "access_url": "<source-url>",
    "retrieved_at": "<timestamp>",
    "version_hash": "<hash>"
  },
  "run_config": {
    "profile": "evaluation",
    "config_digest": "<digest>",
    "authorized_recipients": [
      "Agnes"
    ],
    "limits": {
      "main_requests": 3,
      "repair_requests": 1,
      "attempts_per_request": 2,
      "supplemental_rounds": 1
    }
  },
  "evidence_candidates": [],
  "decision": null,
  "execution": [
    {
      "stage": "query_generation",
      "span_id": "example-call-span",
      "tool": "model_gateway",
      "status": "error",
      "error_code": "UPSTREAM_TIMEOUT",
      "duration_ms": 2000,
      "round": 0,
      "request_id": "example-request"
    }
  ],
  "model_calls": [
    {
      "request_id": "example-request",
      "purpose": "query_generation",
      "round": 0,
      "model_alias": "paper-default",
      "prompt_version": "<version>",
      "params_digest": "<digest>",
      "context_paragraph_ids": [],
      "repairs_request_id": null,
      "attempts": [
        {
          "attempt_id": "example-attempt-1",
          "attempt_index": 1,
          "span_id": "example-span-1",
          "gateway_request_id": null,
          "upstream_response_id": null,
          "configured_model": "agnes-2.5-flash",
          "deployment_id": "agnes-primary",
          "recipient": "Agnes",
          "response_model": null,
          "verified_model_version": null,
          "recovery_kind": "none",
          "recovery_reason": null,
          "status": "error",
          "error_code": "UPSTREAM_TIMEOUT",
          "duration_ms": 1000,
          "usage": null
        },
        {
          "attempt_id": "example-attempt-2",
          "attempt_index": 2,
          "span_id": "example-span-2",
          "gateway_request_id": null,
          "upstream_response_id": null,
          "configured_model": "agnes-2.5-flash",
          "deployment_id": "agnes-primary",
          "recipient": "Agnes",
          "response_model": null,
          "verified_model_version": null,
          "recovery_kind": "retry",
          "recovery_reason": "UPSTREAM_TIMEOUT",
          "status": "error",
          "error_code": "UPSTREAM_TIMEOUT",
          "duration_ms": 1000,
          "usage": null
        }
      ]
    }
  ]
}
```

### 外部评审的返回值

**规则**：仓库外的评审 agent 使用这份结构写下缺陷分析。字段使用故障归因结论，不复用结果标签。`insufficient_evidence` 表示诊断证据不够，不等于结果标签「证据不足」。这份返回值不回写任务状态。

| 字段 | 内容 |
| --- | --- |
| `outcome` | `confirmed`、`suspected` 或 `insufficient_evidence`。 |
| `findings[].stage` | [阶段标识](#3-阶段)。 |
| `findings[].error_code` | [错误码](#4-错误码)。 |
| `findings[].observation` | 已观察到的异常。 |
| `findings[].evidence_refs` | 引用的 `span_id`、段落标识或诊断包字段路径。 |
| `findings[].cause_hypothesis` | 可能根因。 |
| `findings[].reproduction_steps` | 只读复现步骤。 |
| `findings[].regression_assertion` | 回归断言。 |
| `findings[].uncertainty` | 仍不能确定的部分。 |

**规则**：只有复现步骤或确定性校验支持时，`outcome` 才能是 `confirmed`。只有模型解释时必须是 `suspected`。评测按这些字段核对隐藏真因和引用是否有效。一段自由文本的“看起来合理”不算通过。外部评审默认只读，不修改论文、仓库、任务或来源缓存。

```json
{
  "outcome": "suspected",
  "findings": [
    {
      "stage": "retrieval",
      "error_code": "RETRIEVAL_EMPTY",
      "observation": "<observed-anomaly>",
      "evidence_refs": ["<span-id-or-paragraph-id-or-json-path>"],
      "cause_hypothesis": "<hypothesis>",
      "reproduction_steps": ["<read-only-step>"],
      "regression_assertion": "<assertion>",
      "uncertainty": "<what-remains-unknown>"
    }
  ]
}
```

## 7. 角色

本仓库只有一类要实现的 agent。路径一的评审在仓库外完成。

| 名称 | 属于 | 职责 |
| --- | --- | --- |
| paper agent | 本仓库实现的唯一 agent，包在 `agents/` | 在已确认的来源片段上提出判断和摘录。在预算内生成查询、提出判断或申请一次补充检索；必要时修复输出。 |
| 外部评审 agent | 不在本仓库实现。例如 Claude、Cursor | 按 [测试方案](test-plan.md) 阅读诊断包和轨迹，并返回上一节的结构。不是 `agents/` 里的模块，也不进入用户核验流程。 |
