# 术语表

状态：设计稿  
版本：0.3  
日期：2026-09-27  
作者：Wynn  
读者：产品、实现与评测  
相关文档：[产品需求](prd.md)、[架构设计](architecture.md)、[测试方案](test-plan.md)、[技术选型](tech-stack.md)

本文是结果标签、任务状态、阶段、错误码和诊断包字段的唯一登记处。其他文档只链接到这里，不另写定义。

句子标记也只在这里说明：

- **规则**：设计稿里已经决定、实现时要遵守的行为。
- **假设**：要等实验才能判断是否成立的研究命题。见 [研究评测](evaluation.md)。
- **排除**：明确不在范围内的能力。
- **待决**：尚未选择，须由后续实验或评审决定的点。见 [技术选型](tech-stack.md#待决)。

## 1. 结果标签

**规则**：界面展示下面六种结果。前五种写入任务的学术或来源结果；「执行失败」是 `FAILED` 的界面说法，不写入学术标签字段。

| 展示结果 | 使用条件 | 任务状态 | 与 [AGENTS.md](../AGENTS.md) 的对应 |
| --- | --- | --- | --- |
| 支持 | 所指定文献的可定位原文，在相同对象和条件下支持该论断 | `COMPLETED` | 与协作规范中的「支持」相同 |
| 部分支持 | 原文支持主张的一部分，但数量、对象、因果性或适用范围存在重要差异 | `COMPLETED` | 协作规范未单列 |
| 相矛盾 | 原文在对应条件下明确给出相反证据。没有检索到支持片段时不得使用 | `COMPLETED` | 协作规范中的「反驳」对应该标签 |
| 证据不足 | 已取得并处理获许可的目标全文，但现有可核查片段不足以作出前三类判断。检索没有候选时，paper agent 也使用本标签。表述为本次未获得足够证据，不能宣称文献绝对没有证据 | `COMPLETED` | 与协作规范中的「证据不足」相同 |
| 无法核验来源 | DOI 或文献身份无法确认、无合规全文、版本或许可不能自动处理、提取完整性不足 | `BLOCKED` | 协作规范未单列 |
| 执行失败 | 外部接口、任务执行或模型输出校验失败。这不是学术判断 | `FAILED` | 协作规范未单列 |

paper agent 写出的标签只表示通过 [证据门槛](#5-证据门槛)，不是客观真值。仓库外的评审 agent 可以不同意该标签，但不得因此改写任务状态。

## 2. 任务状态

**规则**：任务状态与结果标签分开存储。下表是全部状态。

| 状态 | 含义 | 终态 |
| --- | --- | --- |
| `QUEUED` | 已入队，尚未执行 | 否 |
| `RUNNING` | 正在执行 | 否 |
| `COMPLETED` | 流程结束并写入结果标签。paper agent 记下「证据不足」时也是本状态 | 是 |
| `BLOCKED` | 来源身份、许可或完整性未通过。检索为空不属于本状态 | 是 |
| `FAILED` | 执行错误。不映射成「相矛盾」或「证据不足」 | 是 |
| `INTERRUPTED` | 进程启动时，把遗留的 `RUNNING` 改成的状态 | 是 |

**规则**：重试不改原任务状态，而是新建一条 `QUEUED` 任务，并保留原记录。只有终态任务可以重试或删除。paper agent 不因外部不同意而增加任务状态。分歧只写在缺陷分析里。

## 3. 阶段

**规则**：界面进度与诊断包里的 `execution.stage` 使用同一组标识。

| 阶段标识 | 界面文字 |
| --- | --- |
| `wait` | 等待 |
| `source_identity` | 核对来源 |
| `license` | 检查许可 |
| `fetch` | 获取全文 |
| `retrieval` | 检索证据 |
| `decision` | 判断 |
| `evidence_validation` | 证据校验 |

## 4. 错误码

**规则**：错误码表示机器可读的原因。它决定任务状态和结果标签，不单独成为第三套学术结论。

| 错误码 | 条件 | 任务状态 | 结果标签 |
| --- | --- | --- | --- |
| `SOURCE_MISMATCH` | DOI 指向不同论文，或 PMCID 与 DOI 不一致。不改用另一篇相似文献 | `BLOCKED` | 无法核验来源 |
| `LICENSE_UNKNOWN` | 许可缺失、版本间许可冲突，或不在 [D9](tech-stack.md#d9-文献来源) 允许的自动处理范围内 | `BLOCKED` | 无法核验来源 |
| `CONTENT_INCOMPLETE` | JATS 缺失、解析失败，或结论依赖未能可靠读取的表格、图像。摘要和参考文献列表不能代替目标全文 | `BLOCKED` | 无法核验来源 |
| `RETRIEVAL_EMPTY` | 限定文献的检索没有可供判断的候选。paper agent 不为此再调用模型 | `COMPLETED` | 证据不足 |
| `UPSTREAM_TIMEOUT` | 外部请求超时或限流 | `FAILED` | 执行失败 |
| `MODEL_INVALID_OUTPUT` | 模型输出未通过结构校验。允许一次受控重试，仍然无效时使用本码 | `FAILED` | 执行失败 |
| `QUOTE_MISMATCH` | 摘录不能在同版本原文段落中逐字找到，或证据指向了错误来源 | `FAILED` | 执行失败 |

**待决**：超时和限流目前共用 `UPSTREAM_TIMEOUT`。是否拆成两个错误码，见 [技术选型的待决项](tech-stack.md#待决)。

## 5. 证据门槛

**规则**：「证据门槛」只表示能否展示确定判断。确定判断指「支持」「部分支持」「相矛盾」。

展示确定判断须同时满足：目标 DOI 与 PMCID 身份一致、所用版本和许可可记录、摘录能在保存的同版本段落中逐字定位、结构校验通过。不要求仓库内的第二名 agent 表示同意。

未通过时按原因进入下表，不一律写成 `BLOCKED`：

| 原因 | 任务状态 | 结果标签 |
| --- | --- | --- |
| 来源身份、许可或完整性未通过 | `BLOCKED` | 无法核验来源 |
| 全文已处理但证据不够，或检索没有候选 | `COMPLETED` | 证据不足 |
| 输出校验失败 | `FAILED` | 执行失败 |

## 6. 诊断包

**规则**：输入诊断包和外部评审的返回值是两份结构。输入包不包含 `diagnosis`，也不包含故障注入真因或正式评测标签。那些记录只由评测器保存。

默认外传包遮盖未发表论断。没有原句时，外部评审不得声称核实了语义标签。完整语义包须在作者授权范围内提供论断原句和可复查的获许可片段，并写明接收方。

外部评审不在本仓库实现。Claude、Cursor 等只出现在 [测试方案](test-plan.md) 中，不是 `agents/` 里的模块，也不出现在字段名里。

### 输入诊断包

`schema_version` 当前为 `1.0`。字段指向本地冻结的任务和来源快照。

| 字段 | 内容 |
| --- | --- |
| `schema_version` | 结构版本。当前取值 `1.0`。 |
| `case_id` | 任务标识。 |
| `run_id` | 一次运行的标识。 |
| `trace_id` | 对应轨迹的标识。 |
| `input.doi` | 标准化 DOI。 |
| `input.claim` | 论断文本。`privacy` 为 `redacted` 时使用占位，不放未发表原句。 |
| `input.privacy` | `redacted` 或 `consented`。 |
| `source.title` | 题名。 |
| `source.doi` | 来源 DOI。 |
| `source.pmcid` | PMCID。 |
| `source.license` | 已核对的许可。 |
| `source.version` | 全文版本。 |
| `source.access_url` | 获取入口。 |
| `source.retrieved_at` | 获取时间。 |
| `source.version_hash` | 内容哈希。 |
| `evidence_candidates[].agent` | 固定为 `paper`。本仓库只有 paper agent。 |
| `evidence_candidates[].paragraph_id` | 段落标识。 |
| `evidence_candidates[].section` | 章节。 |
| `evidence_candidates[].rank` | 检索排名。 |
| `evidence_candidates[].quote` | 获许可的逐字摘录。 |
| `evidence_candidates[].paragraph_hash` | 段落哈希。 |
| `evidence_candidates[].source_url` | 原文位置链接。 |
| `evidence_candidates[].entered_context` | 该段落是否进入模型上下文。 |
| `decisions[].agent` | 固定为 `paper`。 |
| `decisions[].label` | 结果标签中的前五种之一，不含「执行失败」。 |
| `decisions[].cited_paragraph_ids` | 理由所引用的段落标识。 |
| `decisions[].validation` | `pass` 或 `fail`。 |
| `decisions[].disagreement` | paper agent 不写内部分歧，固定为 `null`。外部评审的不同意见不回写本字段。 |
| `decisions[].rejection_reason` | 拒判原因。没有时为 `null`。 |
| `execution[].stage` | [阶段标识](#3-阶段)。 |
| `execution[].span_id` | 对应 span。 |
| `execution[].tool` | 工具名。 |
| `execution[].status` | 该步骤自身的结果，例如调用成功或失败。不使用任务状态枚举。 |
| `execution[].error_code` | [错误码](#4-错误码)，没有时为 `null`。 |
| `execution[].duration_ms` | 耗时，单位毫秒。 |
| `execution[].prompt_version` | 提示词版本。不放完整提示词。 |
| `execution[].model_id` | 实际模型标识。 |
| `execution[].retry_count` | 该步骤已发生的重试次数。 |
| `execution[].params_digest` | 已脱敏的参数摘要。 |

下面的 JSON 与上表是同一形状。值都是占位符，不是运行记录。

```json
{
  "schema_version": "1.0",
  "case_id": "<case-id>",
  "run_id": "<run-id>",
  "trace_id": "<trace-id>",
  "input": {
    "doi": "<normalized-doi>",
    "claim": "<redacted-or-consented-text>",
    "privacy": "redacted"
  },
  "source": {
    "title": "<title>",
    "doi": "<normalized-doi>",
    "pmcid": "<pmcid>",
    "license": "<verified-license>",
    "version": "<version>",
    "access_url": "<access-url>",
    "retrieved_at": "<timestamp>",
    "version_hash": "<hash>"
  },
  "evidence_candidates": [
    {
      "agent": "paper",
      "paragraph_id": "<id>",
      "section": "<section>",
      "rank": 1,
      "quote": "<licensed-excerpt>",
      "paragraph_hash": "<hash>",
      "source_url": "<url>",
      "entered_context": true
    }
  ],
  "decisions": [
    {
      "agent": "paper",
      "label": "<label>",
      "cited_paragraph_ids": ["<id>"],
      "validation": "pass",
      "disagreement": null,
      "rejection_reason": null
    }
  ],
  "execution": [
    {
      "stage": "retrieval",
      "span_id": "<span-id>",
      "tool": "fts5",
      "status": "<status>",
      "error_code": null,
      "duration_ms": 0,
      "prompt_version": "<prompt-version>",
      "model_id": "<model-id>",
      "retry_count": 0,
      "params_digest": "<redacted-digest>"
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
| paper agent | 本仓库实现的唯一 agent，包在 `agents/` | 在已确认的来源片段上提出判断和摘录。一次核验只调用一次模型。 |
| 外部评审 agent | 不在本仓库实现。例如 Claude、Cursor | 按 [测试方案](test-plan.md) 阅读诊断包和轨迹，并返回上一节的结构。不是 `agents/` 里的模块，也不进入用户核验流程。 |
