# 真实来源集语义指标记录（#86 人工答案 × 真实模型，非门禁产物）

> 本文件由 `tests/functional/live_metrics.py` 生成，**不参与 CI**，也**不逐字节可复现**。
> 它跑的是 `tests/functional/sources/` 的真实来源集（`#86` 人工答案集），
> 分母与对账规则完全取自 `report.metrics`（`docs/evaluation.md` §4），本文件不另造口径。
> 它与 `docs/semantic-report.md`（回放、逐字节可比对、CI 门禁）分工不同，
> 引用时必须带上本文件顶部的生成时间与模型名。

## 本次运行

| 项 | 值 |
| --- | --- |
| 生成时间 | 2026-10-22T15:32:29+08:00 |
| 运行所在提交 | `be200f4e61162d56c38f12d1054f79de44731e47` |
| `PAPER_EVIDENCE_PROVIDER_MODEL` | `deepseek/deepseek-flash` |
| 上游回报的模型 | `deepseek-flash` |
| 提示词版本（`PaperPromptBuilder.version`） | `paper-prompt-0.2.3` |
| 答案集 | `tests/functional/sources/`，4 篇来源、N = 24（全部签核 `agree`） |
| 答案集指纹 | `6b801235496a73e1` |
| 余额（前 → 后） | 15.10 → 14.98 |
| 密钥来源 / 账号 | DeepSeek key（用户另行提供，与 #115 同一把；余额约 CNY 15.3）。非本机 deepseek_token.txt 那把（本机实测 CNY 3.52） |
| 本轮模型输出来源 | 见 `docs/metrics-live-86.run.json`（**未重跑模型**，只按当前答案集重算指标） |

复现命令（需网络与凭据，会真实计费）：

```bash
PAPER_EVIDENCE_PROVIDER_MODEL=<provider/model> \
PAPER_EVIDENCE_MODEL_API_KEY=<key> \
PAPER_EVIDENCE_MODEL_KEY_LABEL='<哪把 key / 哪个账号>' \
  python tests/functional/live_metrics.py
```

只重算、不重跑（答案集改签后用这条）：

```bash
  python tests/functional/live_metrics.py --from docs/metrics-live-86.run.json
```

> **与 `#115` 的关系**：两轮**独立运行、互不替代**——`#115` 跑 7 例构造样本（提示词验收），
> 本记录跑 4 篇真实来源的 24 条签核答案（指标）。`#110` 原先「本机 key + `deepseek-chat` 只跑一轮」
> 的要求已由项目负责人作废（2026-10-22），以这两轮实测为准。

## 这份记录不能被读成什么

- **不是可复现证据**。引用时必须带上生成时间与模型名；CI 不跑它，也不该跑。
- **不是总体准确率**。N = 24，单次抽样，指标只在本次有限验收集内成立。
- **真值是单人复核签核的**（`#86` 的 review 字段），不是双人独立标注后的仲裁结果，
  分歧解决前不构成正式真值（`docs/evaluation.md` §2 的标注规程是研究集的要求，
  首版小规模验收明确不以它为前提）。
- **「标签来源」列里的「工作流降级」不是模型的判断**（有界检索为空时工作流自己返回）。
- **单次抽样，边界样本会抖**：同一模型同一答案集在 2026-10-21 与 2026-10-22 的两轮里，
  `PMC13648980-c04` 一次判「证据不足」一次判「部分支持」（真值：部分支持）。
  这类抖动是真实的，引用单个数字时必须带上日期与轮次，不能当作稳定准确率。

## 1. 执行结果分布（分母对账）

互斥恒等式：`N = D + I + B + F + C + X + U`

| 桶 | 数量 | 含义 |
| --- | --- | --- |
| D | 21 | COMPLETED 且标签为确定判断（支持/部分支持/相矛盾） |
| I | 3 | COMPLETED 且标签为证据不足 |
| B | 0 | BLOCKED |
| F | 0 | FAILED |
| C | 0 | CANCELLED |
| X | 0 | INTERRUPTED |
| U | 0 | QUEUED/RUNNING 及尚未创建的槽位 |

校验：D+I+B+F+C+X+U = 24，与 N 一致。

## 2. 关键指标

| 指标 | 值 | 分子/分母 |
| --- | --- | --- |
| 可判定覆盖率（全批次） | 87.5% | 21/24 |
| 可判定覆盖率（真值可判定子集） | 100.0% | 20/20 |
| 语义标签正确数/总数 | 22/24 | — |
| 证据冲突识别率（相矛盾 recall） | 1.00 | 6/6 |
| macro-F1（真值可判定三类等权） | 0.92 | 参与：支持、部分支持、相矛盾 |
| 应拒判集错误确定判断率 | 0.25 | 1/4（R 总数 4） |

### 2.1 结构哨兵：摘录定位有效率（**不是质量指标**）

| 项 | 值 | 说明 |
| --- | --- | --- |
| 摘录定位有效率 | 100.0%（44/44） | 由 `COMPLETED` 的定义保证：发布前每条 evidence 都过 `QUOTE_MISMATCH` 校验 |

这一栏**单列**，不与上面的质量指标并列读：`COMPLETED` 的前提就是每条引文已通过校验，
脚本再对冻结文本复核一遍，只要校验没坏就恒等 100%。它是有用的回归哨兵——
哪天不在 100%，说明阻塞链路坏了——但它不含 FP/FN，不能当作「引文质量好」的证据。

## 3. 逐标签 precision / recall

`precision = TP/(TP+FP)`、`recall = TP/(TP+FN)`；真值为该类但系统**拒判或执行失败**的样本计入该类 FN，不从分母移除。

| 标签 | 真实样本数 | 预测数 | TP | FP | FN | precision | recall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 支持 | 9 | 8 | 8 | 0 | 1 | 1.00 | 0.89 |
| 部分支持 | 5 | 6 | 5 | 1 | 0 | 0.83 | 1.00 |
| 相矛盾（单列） | 6 | 7 | 6 | 1 | 0 | 0.86 | 1.00 |
| 证据不足 | 4 | 3 | 3 | 0 | 1 | 1.00 | 0.75 |

## 4. macro-F1（真值可判定三类，等权）

| 类别 | F1 |
| --- | --- |
| 支持 | 0.94 |
| 部分支持 | 0.91 |
| 相矛盾 | 0.92 |
| **macro-F1** | **0.92** |

参与平均的类别：支持、部分支持、相矛盾。

## 5. 应拒判样本上的错误确定判断率

R 为独立标注（签核）为证据不足的样本集合，不按系统输出倒推。

| 项目 | 值 |
| --- | --- |
| R 总数 | 4 |
| R 中 COMPLETED | 4 |
| R 中输出确定判断（错误确定判断） | 1 |
| 错误确定判断率（/ COMPLETED） | 0.25 |
| 全批次发生率（/ R 总数） | 0.25 |

误判（真值可判定却判成别的确定标签）：`PMC13648980-c01`。

## 6. 逐条结果

| case | 期望标签 | 实际标签 | 标签来源 | 终态 | 错误码 | 发布引文（定位/总数） | 用时 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `PMC1182327-c01` | 支持 | 支持 | 模型判定 | COMPLETED | — | 2/2 | 11.8s |
| `PMC1182327-c02` | 支持 | 支持 | 模型判定 | COMPLETED | — | 2/2 | 6.9s |
| `PMC1182327-c03` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1/1 | 7.5s |
| `PMC1182327-c04` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1/1 | 7.3s |
| `PMC1182327-c05` | 部分支持 | 部分支持 | 模型判定 | COMPLETED | — | 1/1 | 8.5s |
| `PMC1182327-c06` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1/1 | 7.8s |
| `PMC13648980-c01` | 支持 | 部分支持 | 模型判定 | COMPLETED | — | 3/3 | 14.8s |
| `PMC13648980-c02` | 支持 | 支持 | 模型判定 | COMPLETED | — | 3/3 | 14.5s |
| `PMC13648980-c03` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 3/3 | 10.9s |
| `PMC13648980-c04` | 部分支持 | 部分支持 | 模型判定 | COMPLETED | — | 4/4 | 44.4s |
| `PMC13648980-c05` | 证据不足 | 相矛盾 | 模型判定 | COMPLETED | — | 2/2 | 8.3s |
| `PMC13648980-c06` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 2/2 | 14.0s |
| `PMC13648980-c07` | 证据不足 | 证据不足 | 模型判定 | COMPLETED | — | 3/3 | 9.2s |
| `PMC13648980-c08` | 部分支持 | 部分支持 | 模型判定 | COMPLETED | — | 2/2 | 16.0s |
| `PMC7461750-c01` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1/1 | 6.6s |
| `PMC7461750-c02` | 证据不足 | 证据不足 | 模型判定 | COMPLETED | — | 0/0 | 10.3s |
| `PMC7461750-c03` | 证据不足 | 证据不足 | 模型判定 | COMPLETED | — | 0/0 | 4.8s |
| `PMC8806060-c01` | 支持 | 支持 | 模型判定 | COMPLETED | — | 3/3 | 10.6s |
| `PMC8806060-c02` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1/1 | 6.1s |
| `PMC8806060-c03` | 支持 | 支持 | 模型判定 | COMPLETED | — | 2/2 | 5.6s |
| `PMC8806060-c04` | 部分支持 | 部分支持 | 模型判定 | COMPLETED | — | 2/2 | 15.2s |
| `PMC8806060-c05` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1/1 | 6.9s |
| `PMC8806060-c06` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1/1 | 7.3s |
| `PMC8806060-c07` | 部分支持 | 部分支持 | 模型判定 | COMPLETED | — | 3/3 | 15.0s |

| 汇总 | 值 |
| --- | --- |
| 标签与人工答案一致 | **22 / 24** |
| 其中模型自行判断 | 24 / 24 |
| **模型判定且一致** | **22 / 24** |

## 7. 原始输出（每次模型调用）

保留原始输出是为了定位：只剩一句错误码时无法判断是模型判错还是输出形状不合契约。
每次调用同时记 `response_model` 与 token 用量——没有它们，「20/24」说不清是哪个模型、哪版提示词的产出（`evaluation.md` §4）。

### `PMC1182327-c01` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 146 / completion 419 / total 565、解析通过</summary>

```text
{"queries":["most published research findings are false","published research findings are false","most published findings are false","majority of published research findings are false","false published research findings","most published research findings are not true"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3483 / completion 1496 / total 4979、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选片段明确陈述大多数当代已发表/声称的研究发现为假，并称可证明这一点，与论断在对象和数量上吻合。","supported_parts":["大多数已发表的研究发现是错的"],"scope_differences":[],"limitations":["原文中的表述带有‘current/claimed’限定，且属于论文的论证性结论"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"most current published research findings are false"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:2","quote":"most claimed research findings are false"}]}}
```

</details>

### `PMC1182327-c02` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 151 / completion 176 / total 327、解析通过</summary>

```text
{"queries": ["small sample size research field findings true probability", "smaller sample size lower probability findings true", "sample size research field probability findings are true", "small sample size lower probability true findings", "research field sample size findings true"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3326 / completion 787 / total 4113、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文的推论1直接表述：研究领域中所做研究越小，研究发现为真的可能性越低；摘要也重复了同一方向，与论断的对象、方向和范围一致。","supported_parts":["研究领域的样本量（研究规模）越小，其研究发现为真的可能性越低。"],"scope_differences":[],"limitations":["该证据是模型框架下的推论性表述，并强调在其他因素相同的前提下成立。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:14","quote":"Corollary 1: The smaller the studies conducted in a scientific field, the less likely the research findings are to be true."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"In this framework, a research finding is less likely to be true when the studies conducted in a field are smaller"}]}}
```

</details>

### `PMC1182327-c03` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 155 / completion 407 / total 562、解析通过</summary>

```text
{"queries":["flexibility in research design definitions outcomes and analysis","likelihood that research findings are true","greater flexibility lower likelihood findings are true","research design flexibility definitions outcomes analysis","research findings true probability flexibility"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3989 / completion 621 / total 4610、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文的推论4直接表述：科学领域中设计、定义、结局和分析方式的灵活性越大，研究发现为真的可能性越低，与作者论断完全一致。","supported_parts":["研究设计、定义、结局与分析方式的灵活性越大，研究发现为真的可能性越低"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:17","quote":"Corollary 4: The greater the flexibility in designs, definitions, outcomes, and analytical modes in a scientific field, the less likely the research findings are to be true."}]}}
```

</details>

### `PMC1182327-c04` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 148 / completion 330 / total 478、解析通过</summary>

```text
{"queries":["selective outcome reporting randomized controlled trials","outcome reporting bias randomized controlled trials","selective reporting of outcomes in randomized trials","no selective outcome reporting in randomized controlled trials","absence of selective outcome reporting randomized trials","all prespecified outcomes reported randomized controlled trials","outcome reporting bias not present randomized trials","selective outcome reporting does not occur randomized trials"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3658 / completion 686 / total 4344、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确指出，即便在随机对照试验中，选择性结局报告仍是常见问题，直接否定“不会出现”的绝对论断。","supported_parts":[],"scope_differences":[],"limitations":["该片段为概括性引证陈述，未给出具体发生率或试验清单。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:17","quote":"there is strong evidence that selective outcome reporting, with manipulation of the outcomes and analyses reported, is a common problem even for randomized trails [25]."}]}}
```

</details>

### `PMC1182327-c05` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 150 / completion 658 / total 808、解析通过</summary>

```text
{"queries":["randomized controlled trials conclusions approximately 85 percent true","85 percent of randomized controlled trials conclusions true","randomised controlled trials 85 percent true","RCT conclusions 85 percent true","randomized controlled trial results true 85 percent","randomized controlled trials conclusions true"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3329 / completion 697 / total 4026、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"证据确实给出随机对照试验相关发现约85%为真的数值，但该数值仅适用于设计良好、有足够功效且预研究概率为50%的RCT，不能直接推广为所有RCT结论的真实比例。","supported_parts":["设计良好、有足够功效且预研究概率为50%的随机对照试验中，相关发现最终为真的概率约为85%。"],"scope_differences":["论断泛指随机对照试验的结论；证据限定于设计良好、有足够功效且预研究概率为50%的RCT。"],"limitations":["无法判定设计不良、功效不足、预研究概率不是50%或其他类型RCT结论的真实比例是否也为85%。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:21","quote":"A finding from a well-conducted, adequately powered randomized controlled trial starting with a 50% pre-study chance that the intervention is effective is eventually true about 85% of the time."}]}}
```

</details>

### `PMC1182327-c06` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 150 / completion 334 / total 484、解析通过</summary>

```text
{"queries":["peer review suppression of contrary findings","established researchers suppress refuting research","referees reject studies that refute conclusions","scientific gatekeeping and peer review","peer review bias against refutation","powerful researchers blocking publication","reviewers suppress evidence contradicting conclusions","peer review cannot suppress refuting studies","authority and bias in peer review","scientific consensus and peer review"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3716 / completion 730 / total 4446、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确称知名研究者可能通过同行评审压制反驳其结论的研究，与论断“无法压制”方向相反。","supported_parts":[],"scope_differences":["论断使用绝对否定“无法”，原文使用“may suppress”表示可能发生；但二者在能否压制这一核心关系上相反。"],"limitations":["原文表述为“may”，未提供该行为普遍发生的定量证据；但足以反驳绝对“无法”的论断。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:18","quote":"Prestigious investigators may suppress via the peer review process the appearance and dissemination of findings that refute their findings, thus condemning their field to perpetuate false dogma."}]}}
```

</details>

### `PMC13648980-c01` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 162 / completion 409 / total 571、解析通过</summary>

```text
{"queries":["rPMS treatment duration pain intensity VAS","rPMS four week intervention pain intensity","repetitive peripheral magnetic stimulation pain intensity VAS","both rPMS treatment durations reduced pain","four week rPMS intervention VAS score","rPMS significantly reduced pain intensity","rPMS 4-week intervention period pain intensity"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 2765 / completion 2341 / total 5106、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"证据显示两种 rPMS 治疗时长（10 分钟与 15 分钟）在 4 周干预期内均观察到 VAS 疼痛强度显著改善，但原文同时明确指出两组均接受 active rPMS 联合标准化牵伸训练，且无假刺激对照，不能把 VAS 下降归因于 rPMS 本身，因此仅部分支持该因果性论断。","supported_parts":["两种 rPMS 治疗时长（10 分钟与 15 分钟）在 4 周干预期内均观察到 VAS 疼痛强度显著改善","VAS 在 4 周干预期内存在显著时间效应"],"scope_differences":["论断将 VAS 降低归因于 rPMS 治疗时长，但证据仅支持两种主动方案均伴随 VAS 改善，不能确认 rPMS 本身的因果疗效","证据中的改善发生在 rPMS 联合标准化牵伸训练的背景下，非单独 rPMS 暴露"],"limitations":["缺乏假刺激对照，无法判定 rPMS 本身对 VAS 的独立疗效","原文明确提示结果应解释为两种主动治疗方案之间的比较，而非 rPMS 疗效证据"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","quote":"LMMs demonstrated significant time effects for VAS, PPT, and NDI (all p < 0.001), indicating significant improvements across the 4-week intervention period."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","quote":"Importantly, because both groups received active rPMS combined with standardized stretching exercises, the present findings should be interpreted as a comparison between two active treatment protocols rather than as evidence confirming the efficacy of rPMS itself."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:50","quote":"Both treatment durations were associated with significant short-term improvements in pain intensity, pressure pain threshold, and neck-related disability in individuals with upper trapezius MPS."}]}}
```

</details>

### `PMC13648980-c02` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 176 / completion 312 / total 488、解析通过</summary>

```text
{"queries":["VAS score decreased from baseline at week 2 by 3.02 points","VAS score decreased from baseline at week 4 by 4.87 points","visual analog scale week 2 change 3.02","visual analogue scale week 4 change 4.87","VAS reduction during intervention week 2 week 4","visual analog scale continuously decreased during intervention"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3721 / completion 2351 / total 6072、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选段落明确报告 VAS 随时间显著下降，并给出与论断一致的第 2 周较基线降低 3.02 分、第 4 周降低 4.87 分。","supported_parts":["VAS 在干预期内随时间下降","第 2 周较基线降低 3.02 分","第 4 周较基线降低 4.87 分"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:34","quote":"A significant main effect of time was observed."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:34","quote":"VAS decreased by 3.02 points at week 2"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:34","quote":"by 4.87 points at week 4"}]}}
```

</details>

### `PMC13648980-c03` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 155 / completion 611 / total 766、解析通过</summary>

```text
{"queries":["15 minute rPMS protocol","10 minute rPMS protocol","15-minute versus 10-minute rPMS","rPMS treatment duration comparison","rPMS protocol effectiveness","repetitive peripheral magnetic stimulation 15 minutes","repetitive peripheral magnetic stimulation 10 minutes","frozen shoulder rPMS effectiveness","longer rPMS session more effective","rPMS 15 minutes 10 minutes"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3262 / completion 1190 / total 4452、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"该随机试验直接比较了15分钟与10分钟rPMS方案，结果显示两组在VAS、PPT、NDI上无显著组×时间交互，恢复轨迹相当，且未检测到方案间显著差异；这与“15分钟方案比10分钟方案更有效”的优越性论断相反。","supported_parts":[],"scope_differences":["证据针对上斜方肌肌筋膜疼痛综合征患者、每周1次共4周干预及短期随访；论断未限定人群、疗程和结局范围。"],"limitations":["证据仅覆盖该试验的样本、上斜方肌MPS、4周干预及短期VAS/PPT/NDI结局；不能判定其他rPMS参数、其他人群或长期效果。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","quote":"no significant group-by-time interaction was observed for any outcome, suggesting that both stimulation durations produced comparable recovery trajectories."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:47","quote":"The absence of duration-dependent differences indicates that rPMS efficacy may depend more on adequate proprioceptive afferent recruitment and cumulative pulse delivery than on total stimulation duration"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:50","quote":"No significant between-protocol differences were detected within the present sample and follow-up period."}]}}
```

</details>

### `PMC13648980-c04` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 152 / completion 284 / total 436、解析通过</summary>

```text
{"queries":["10 minute protocol 15 minute protocol","10 minute regimen versus 15 minute regimen","numerically superior 10 minutes 15 minutes","ten minute protocol better than fifteen minute protocol","10 min versus 15 min protocol"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3211 / completion 1792 / total 5003、解析通过</summary>

```text
{"action":"retrieve","queries":["Protocol A 15-minute Protocol B 10-minute rPMS VAS PPT NDI mean values group-by-time results","10-minute versus 15-minute rPMS numerical differences VAS PPT NDI upper trapezius MPS","between-group differences 10-minute 15-minute rPMS week 4 results table"],"neighbor_paragraph_ids":["p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:30"]}
```

</details>

<details><summary>第 3 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 5991 / completion 6124 / total 12115、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"原文显示10分钟组在VAS、PPT、NDI的4周调整后均值上数值更有利，但同时明确无显著组间差异、恢复轨迹相当；PPT从基线到4周的改善量两组相同，因此只部分支持“10分钟方案在数值上优于15分钟方案”的概括。","supported_parts":["10分钟方案在4周调整后均值上，VAS和NDI低于15分钟方案，PPT高于15分钟方案，方向数值更有利"],"scope_differences":["证据仅针对上斜方肌肌筋膜疼痛综合征、4周rPMS干预及短期VAS/PPT/NDI结局，不能外推到更广人群、长期效果或其他方案","数值方向差异均未达统计学显著，不能等同于真实疗效优越"],"limitations":["PPT从基线的改善量两组相同（均约2.51 kg/cm²），不支持PPT疗效数值更优","原文报告无显著组间差异，95%CI均包含0"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:34","quote":"Adjusted marginal means declined from 6.67 (95% CI 6.23–7.10) to 1.80 (95% CI 1.32–2.28) in Protocol A and from 6.55 (95% CI 6.10–6.99) to 1.53 (95% CI 1.05–2.00) in Protocol B (Table 3)."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:39","quote":"Adjusted marginal means increased from 6.73 (95% CI 6.15–7.32) at baseline to 9.24 (95% CI 8.63–9.85) at week 4 in Protocol A, and from 6.90 (95% CI 6.31–7.48) to 9.41 (95% CI 8.79–10.02) in Protocol B (Table 3)."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:40","quote":"Adjusted marginal means declined from 14.27 (95% CI 12.49–16.05) at baseline to 5.13 (95% CI 3.25–7.01) at week 4 in Protocol A, and from 14.67 (95% CI 12.89–16.45) to 4.49 (95% CI 2.61–6.37) in Protocol B (Table 3)."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:41","quote":"No significant group effect or group-by-time interaction was observed for any outcome, indicating that the trajectory of improvement did not differ between groups."}]}}
```

</details>

### `PMC13648980-c05` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 161 / completion 439 / total 600、解析通过</summary>

```text
{"queries":["observed clinical improvement rPMS stimulation","clinical improvement attributable to rPMS stimulation","rPMS stimulation itself","concurrent stretching exercises","placebo effect rPMS","improvement not due to stretching exercises","improvement not due to placebo effect","repetitive peripheral magnetic stimulation clinical improvement","rPMS treatment effect clinical improvement","stretching exercise placebo effect"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3604 / completion 975 / total 4579、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"原文明确指出，由于两组均接受主动 rPMS 联合标准化拉伸，无法确定 rPMS 对观察到的临床改善的独立贡献，且其效应不能与拉伸、情境或安慰效应区分。这与论断将改善归因于 rPMS 本身、排除拉伸和安慰效应的说法相反。","supported_parts":[],"scope_differences":[],"limitations":["该判断基于原文作者对研究设计的说明：未设假刺激组，且两组均接受主动 rPMS 联合标准化拉伸，因此无法分离各成分。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:49","quote":"Because both groups received active rPMS in combination with standardized stretching exercises, the independent contribution of rPMS to the observed clinical improvements could not be determined."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:49","quote":"Consequently, the specific effects of rPMS cannot be distinguished from the effects of stretching exercises or potential contextual and placebo-related influences."}]}}
```

</details>

### `PMC13648980-c06` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 158 / completion 717 / total 875、解析通过</summary>

```text
{"queries":["15-minute rPMS 10-minute rPMS equivalent efficacy","10-minute rPMS versus 15-minute rPMS","rPMS regimen duration efficacy equivalence","repetitive peripheral magnetic stimulation 15 minutes 10 minutes","comparable efficacy 10-minute rPMS protocol","noninferiority 10-minute rPMS 15-minute rPMS","rPMS treatment duration no difference in efficacy","similar outcomes 15-minute rPMS 10-minute rPMS"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3770 / completion 1645 / total 5415、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"原文明确指出该试验未按等效性或非劣效性设计/把握度计算，也未预设等效界值，并强调组间无显著差异不能解释为两种时长等效的正式证据；这与“本研究证明了疗效等效”相反。","supported_parts":["研究直接比较了 15 分钟与 10 分钟两种 rPMS 方案","观察到两组恢复轨迹相近且无显著组间×时间交互"],"scope_differences":["原文仅显示 4 周随访内、上斜方肌 MPS 患者中两种主动 rPMS 方案的结局相近，并非正式疗效等效性证明"],"limitations":["未设等效/非劣效界值","不能排除联合拉伸及非特异效应","随访仅 4 周"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:49","quote":"the study was not designed or powered as an equivalence or noninferiority trial and did not prespecify an equivalence or noninferiority margin. Therefore, the absence of significant between-group differences should not be interpreted as formal evidence of equivalence between treatment durations [52]."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","quote":"no significant group-by-time interaction was observed for any outcome, suggesting that both stimulation durations produced comparable recovery trajectories."}]}}
```

</details>

### `PMC13648980-c07` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 157 / completion 341 / total 498、解析通过</summary>

```text
{"queries": ["rPMS long-term clinical efficacy", "repetitive peripheral magnetic stimulation long-term effect", "rPMS effect maintained after four weeks", "four-week intervention long-term maintenance", "clinical efficacy sustained after treatment", "follow-up after four-week rPMS intervention", "long-term maintenance of treatment effect", "rPMS frozen shoulder follow-up efficacy"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 2896 / completion 1261 / total 4157、解析通过</summary>

```text
{"action":"final","decision":{"label":"证据不足","rationale":"候选片段仅报告4周干预期内及第4周终点的评估结果，没有提供干预结束后的长期随访数据，且原文明确需要更长期随访来判定。因此无法支持“4周干预结束后仍能长期维持”的论断。","supported_parts":["4周干预期内VAS、PPT、NDI等结局有显著改善"],"scope_differences":["论断关注4周干预结束后的长期维持，证据仅覆盖至第4周治疗期终点"],"limitations":["缺乏干预结束后长期随访数据，无法判定疗效是否长期维持"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:28","quote":"Evaluations were conducted at baseline and at weeks 2 and 4."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","quote":"indicating significant improvements across the 4-week intervention period"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:46","quote":"longer-term follow-up are needed"}]}}
```

</details>

### `PMC13648980-c08` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 150 / completion 372 / total 522、解析通过</summary>

```text
{"queries":["rPMS chronic neck pain","repetitive peripheral magnetic stimulation chronic neck pain","rPMS neck pain effectiveness","repetitive peripheral magnetic stimulation neck pain effectiveness","rPMS treatment chronic neck pain","peripheral magnetic stimulation chronic neck pain","rPMS cervical pain","repetitive peripheral magnetic stimulation cervical pain","magnetic stimulation chronic neck pain"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3322 / completion 1294 / total 4616、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"候选片段提供了 rPMS 对上斜方肌肌筋膜疼痛综合征（慢性颈痛的一种常见来源）具有镇痛和改善颈部残疾的证据，包括随机假对照研究和多疗程研究；但证据集中在特定亚型、特定刺激方案及短期结局，不能支持“对慢性颈痛患者普遍有效”的广泛结论。","supported_parts":["rPMS 在上斜方肌肌筋膜疼痛综合征患者中可显著降低疼痛强度并改善颈部相关残疾","多疗程上斜方肌 rPMS 可改善疼痛、PPT 和触发点特征，且益处可持续一段时间"],"scope_differences":["论断称对“慢性颈痛患者”普遍有效，证据主要局限于上斜方肌肌筋膜疼痛综合征这一特定亚型","证据涉及特定 rPMS 方案（如单次 10 分钟、多疗程上斜方肌刺激）及短期结局，未覆盖所有慢性颈痛病因、病程和治疗参数"],"limitations":["无法判定 rPMS 对其他类型慢性颈痛是否普遍有效","长期疗效、不同刺激参数及更广泛患者人群的普遍性仍不确定"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:9","quote":"In upper trapezius MPS specifically, randomized sham-controlled evidence showed that a single 10-minute rPMS session significantly reduced pain intensity and improved neck-related disability, with peak effects observed on Days 3–4 post-treatment [27]."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:43","quote":"Smania et al. [23] reported significant improvements in pain, PPT, and trigger-point characteristics following multi-session trapezius rPMS, with benefits persisting for up to three months."}]}}
```

</details>

### `PMC7461750-c01` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 161 / completion 524 / total 685、解析通过</summary>

```text
{"queries":["correction notice","Fuchs KoCo19","Dr Fuchs KoCo19","Fuchs KoCo19 collaboration","Fuchs authorship KoCo19","omitted Fuchs KoCo19","original publication omitted Fuchs","KoCo19 collaboration authorship","Fuchs affiliation KoCo19","correction original publication omitted"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 871 / completion 331 / total 1202、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选片段明确说明原发表文献中 Fuchs 博士被错误地遗漏为 KoCo19 合作组成员，与更正声明的论断一致。","supported_parts":["该更正声明指出原发表文献遗漏了 Fuchs 博士","遗漏的是 Fuchs 博士在 KoCo19 合作组中的署名"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:3","quote":"In the publication of the original article [1], the author Dr. Fuchs was erroneously omitted as a collaborator from the KoCo19 collaboration group."}]}}
```

</details>

### `PMC7461750-c02` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 156 / completion 461 / total 617、解析通过</summary>

```text
{"queries": ["cohort study Munich recruitment", "recruited approximately 3000 participants in Munich", "Munich cohort 3000 participants", "participants recruited in Munich", "cohort study about 3000 participants", "recruitment of 3000 participants Munich", "study participants Munich cohort"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 755 / completion 586 / total 1341、解析通过</summary>

```text
{"action":"retrieve","queries":["KoCo19 cohort study Munich approximately 3000 participants recruitment","KoCo19 study 3000 participants Munich cohort"],"neighbor_paragraph_ids":["p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:3"]}
```

</details>

<details><summary>第 3 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 884 / completion 254 / total 1138、解析通过</summary>

```text
{"action":"final","decision":{"label":"证据不足","rationale":"候选片段仅涉及原文更正、作者遗漏及协作组更新，没有提供该队列研究的招募地点或参与者数量信息，无法核验“在慕尼黑招募约3000名参与者”的论断。","supported_parts":[],"scope_differences":[],"limitations":["候选片段未包含研究招募地点、队列规模或参与者数量相关信息。","无法从更正说明和 DOI 判断该队列研究是否在慕尼黑招募约3000人。"],"evidence":[]}}
```

</details>

### `PMC7461750-c03` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 158 / completion 279 / total 437、解析通过</summary>

```text
{"queries":["follow-up completed April June 2020","follow-up between April and June 2020","follow-up period April to June 2020","data collection April to June 2020","study follow-up April 2020","follow up conducted April to June 2020","follow-up completed in 2020","follow-up timing 2020"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 864 / completion 265 / total 1129、解析通过</summary>

```text
{"action":"final","decision":{"label":"证据不足","rationale":"候选片段仅为更正说明，未提及该研究的随访时间，无法核验论断中的“2020 年 4 月至 6 月之间完成随访”。","supported_parts":[],"scope_differences":[],"limitations":["候选片段未涉及研究随访、随访起止时间或 2020 年 4 月至 6 月这一时间范围。"],"evidence":[]}}
```

</details>

### `PMC8806060-c01` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 165 / completion 158 / total 323、解析通过</summary>

```text
{"queries":["DF-Tiny-YOLO mean average precision mAP 99.99%","DF-Tiny-YOLO four-class apple leaf dataset mAP","DF-Tiny-YOLO apple leaf dataset mean average precision","DF-Tiny-YOLO mAP 99.99 apple leaf","four-class apple leaf dataset mAP 99.99","DF-Tiny-YOLO average precision apple leaves"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3525 / completion 1759 / total 5284、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选片段明确报告 DF-Tiny-YOLO 的 mAP 为 99.99%，且同一实验段落说明混淆矩阵为四类（4×4），数据段也列明四类苹果叶图像，因此论断的对象、范围与数值一致。","supported_parts":["DF-Tiny-YOLO 的 mAP 为 99.99%","实验涉及四类苹果叶（含健康叶）数据"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:40","quote":"The matrix results reveal that the model mAP is 99.99%"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:40","quote":"including the classification precision and Recall of four different classes of diseases"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:23","quote":"The data included 300 images of leaves with apple scab, 300 with apple black rot, 275 with apple cedar rust, and 529 healthy leaves, total 1,404 images."}]}}
```

</details>

### `PMC8806060-c02` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 176 / completion 339 / total 515、解析通过</summary>

```text
{"queries":["DF-Tiny-YOLO 1x1 1x1 3x3 convolution kernels","DF-Tiny-YOLO network end convolution kernel sequence","DF-Tiny-YOLO detection accuracy computational complexity","1x1 1x1 3x3 convolution kernels detection accuracy","network end convolution kernels improve detection accuracy","convolution kernel arrangement without increasing computational complexity"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3445 / completion 634 / total 4079、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文明确说明 DF-Tiny-YOLO 在网络末端依次使用 1×1、1×1、3×3 卷积核，并指出其可在不增加计算复杂度的情况下提升检测精度，与论断一致。","supported_parts":["DF-Tiny-YOLO 在网络末端依次使用 1×1、1×1、3×3 卷积核","目的是在不增加计算复杂度的前提下提升检测精度"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:21","quote":"Using 1 × 1, 1 × 1, and 3 × 3 convolution kernels at the network terminals will contribute to reducing the dimension of features and increasing the network depth without increasing computational complexity, thus further improving the detection accuracy."}]}}
```

</details>

### `PMC8806060-c03` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 165 / completion 261 / total 426、解析通过</summary>

```text
{"queries":["1,404 images","1404 images","80% 20% training test split","randomly divided into training and testing sets","training set and test set 80 20","images randomly split training testing"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3763 / completion 526 / total 4289、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文明确说明数据共 1,404 张图像，并随机按 80%:20% 划分为训练集与测试集，与论断对象、条件、范围和数量一致。","supported_parts":["1,404 张图像","按 80%:20% 的比例随机划分为训练集与测试集"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:23","quote":"total 1,404 images."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:23","quote":"The images were randomly divided into training and test sets at a ratio of 80%:20%"}]}}
```

</details>

### `PMC8806060-c04` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 164 / completion 295 / total 459、解析通过</summary>

```text
{"queries": ["DF-Tiny-YOLO compared with Tiny-YOLO", "DF-Tiny-YOLO detection accuracy and detection speed", "DF-Tiny-YOLO improved detection accuracy", "DF-Tiny-YOLO improved detection speed", "original Tiny-YOLO baseline comparison", "Tiny-YOLO DF-Tiny-YOLO performance improvement"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3440 / completion 2688 / total 6128、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"证据显示 DF-Tiny-YOLO 的 mAP、IoU、Recall 高于原始 Tiny-YOLO，但检测速度 280 FPS 与 Tiny-YOLO 相同，因此只支持精度提升，不支持速度提升。","supported_parts":["DF-Tiny-YOLO 的检测精度高于原始 Tiny-YOLO（mAP 提高 0.17%，IoU 提高 10.38%，Recall 提高 0.01）"],"scope_differences":["论断称检测速度也有提升，但证据明确给出检测速度为 280 FPS，与 Tiny-YOLO 相同，未显示速度提升"],"limitations":["证据仅覆盖该文苹果叶片病害检测实验及所报告指标，不能外推到其他数据集或任务"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:39","quote":"The mAP of DF-Tiny-YOLO is 99.99%, which was 0.17% higher than that of Tiny-YOLO. The average IoU was 90.88%, which was 1.59% and 10.38% higher than YOLOV2 and Tiny-YOLO, respectively. Recall was 1.00, which was the same as YOLOV2 and 0.01 higher than Tiny-YOLO."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:39","quote":"The detection speed was 280 FPS, which was the same as that of Tiny-YOLO"}]}}
```

</details>

### `PMC8806060-c05` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 155 / completion 295 / total 450、解析通过</summary>

```text
{"queries":["DF-Tiny-YOLO recall YOLOv2","DF-Tiny-YOLO recall comparison YOLOv2","DF-Tiny-YOLO significantly higher recall","DF Tiny YOLO recall performance","recall of DF-Tiny-YOLO versus YOLOv2","DF-Tiny-YOLO recall improvement over YOLOv2"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3272 / completion 367 / total 3639、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明 DF-Tiny-YOLO 的召回率与 YOLOv2 相同，而非显著高于 YOLOv2。","supported_parts":[],"scope_differences":[],"limitations":["候选片段未报告召回率差异的显著性检验结果，但已明确给出两者召回率相同。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:39","quote":"Recall was 1.00, which was the same as YOLOV2 and 0.01 higher than Tiny-YOLO."}]}}
```

</details>

### `PMC8806060-c06` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 153 / completion 273 / total 426、解析通过</summary>

```text
{"queries": ["DF-Tiny-YOLO recognition performance across four categories", "DF-Tiny-YOLO consistent performance four classes", "DF-Tiny-YOLO four category recognition results", "DF-Tiny-YOLO recognition performance four categories consistent", "DF-Tiny-YOLO class-wise recognition performance"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 3612 / completion 717 / total 4329、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"原文明确称 DF-Tiny-YOLO 对 Apple cedar rust 和健康叶片表现最佳，表明四个类别之间识别表现存在差异，而非一致。","supported_parts":[],"scope_differences":[],"limitations":["该片段未列出四个类别逐类的 precision/Recall 具体数值，但已明确显示类别间表现并不一致。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:40","quote":"the model performs best for Apple cedar rust and healthy leaves."}]}}
```

</details>

### `PMC8806060-c07` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、模型 `deepseek-flash`、用量 prompt 157 / completion 269 / total 426、解析通过</summary>

```text
{"queries":["DF-Tiny-YOLO comparison with mainstream detection models","DF-Tiny-YOLO performs better than detection models","DF-Tiny-YOLO superior performance object detection comparison","DF-Tiny-YOLO experimental results compared with three detection models","DF-Tiny-YOLO outperforms mainstream detectors"]}
```

</details>

<details><summary>第 2 次：purpose=decision、模型 `deepseek-flash`、用量 prompt 4213 / completion 2542 / total 6755、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"片段显示 DF-Tiny-YOLO 仅与 YOLOv2 和 Tiny-YOLO 两个其他模型直接对比并表现更优；未支持其与三个及以上其他主流检测模型对比时更优，因此为部分支持。","supported_parts":["DF-Tiny-YOLO 相对 YOLOv2 和 Tiny-YOLO 表现更优或具有更多优势","对比实验比较了 DF-Tiny-YOLO、YOLOv2 和 Tiny-YOLO"],"scope_differences":["证据直接涉及的对照模型只有 YOLOv2 和 Tiny-YOLO 两个，而论断要求三个及以上其他主流检测模型。"],"limitations":["无法判定 DF-Tiny-YOLO 相对第三个及以上主流检测模型是否更优。","原文说明实验环境限制，难以与更多模型比较。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:45","quote":"Thirdly, the results of comparative experimental exploration showed that among YOLOv2, Tiny-YOLO, the optimized DF-Tiny-YOLO network offered more advantages than the other two models."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:39","quote":"Table 5 compares the experimental results of DF-Tiny-YOLO, YOLOv2, and Tiny-YOLO."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:49","quote":"However, the study is limited by the experimental environment, which makes it difficult to compare with more models."}]}}
```

</details>

