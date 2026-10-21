# 真实来源集语义指标记录（#86 人工答案 × 真实模型，非门禁产物）

> 本文件由 `tests/functional/live_metrics.py` 生成，**不参与 CI**，也**不逐字节可复现**。
> 它跑的是 `tests/functional/sources/` 的真实来源集（`#86` 人工答案集），
> 分母与对账规则完全取自 `report.metrics`（`docs/evaluation.md` §4），本文件不另造口径。
> 它与 `docs/semantic-report.md`（回放、逐字节可比对、CI 门禁）分工不同，
> 引用时必须带上本文件顶部的生成时间与模型名。

## 本次运行

| 项 | 值 |
| --- | --- |
| 生成时间 | 2026-10-21T23:02:55+08:00 |
| 运行所在提交 | `905042dc5be9f52752f46c8bcfc78e6b862a6525` |
| `PAPER_EVIDENCE_PROVIDER_MODEL` | `deepseek/deepseek-flash` |
| 答案集 | `tests/functional/sources/`，N = 24（4 篇来源，全部签核 agree） |
| 答案集指纹 | `d10afbf05f5ec118` |
| 余额（前 → 后） | 15.30 → 15.26 |

复现命令（需网络与凭据，会真实计费）：

```bash
PAPER_EVIDENCE_PROVIDER_MODEL=<provider/model> \
PAPER_EVIDENCE_MODEL_API_KEY=<key> \
  python tests/functional/live_metrics.py
```

## 这份记录不能被读成什么

- **不是可复现证据**。引用时必须带上生成时间与模型名；CI 不跑它，也不该跑。
- **不是总体准确率**。N = 24，单次抽样，指标只在本次有限验收集内成立。
- **真值是单人复核签核的**（`#86` 的 review 字段），不是双人独立标注后的仲裁结果，
  分歧解决前不构成正式真值（`docs/evaluation.md` §2 的标注规程是研究集的要求，
  首版小规模验收明确不以它为前提）。
- **「标签来源」列里的「工作流降级」不是模型的判断**（有界检索为空时工作流自己返回）。

## 1. 执行结果分布（分母对账）

互斥恒等式：`N = D + I + B + F + C + X + U`

| 桶 | 数量 | 含义 |
| --- | --- | --- |
| D | 20 | COMPLETED 且标签为确定判断（支持/部分支持/相矛盾） |
| I | 4 | COMPLETED 且标签为证据不足 |
| B | 0 | BLOCKED |
| F | 0 | FAILED |
| C | 0 | CANCELLED |
| X | 0 | INTERRUPTED |
| U | 0 | QUEUED/RUNNING 及尚未创建的槽位 |

校验：D+I+B+F+C+X+U = 24，与 N 一致。

## 2. 关键指标

| 指标 | 值 | 分子/分母 |
| --- | --- | --- |
| 可判定覆盖率（全批次） | 83.3% | 20/24 |
| 可判定覆盖率（真值可判定子集） | 94.7% | 18/19 |
| 摘录定位有效率 | 100.0% | 34/34 |
| 语义标签正确数/总数 | 20/24 | — |

## 3. 逐标签 precision / recall

`precision = TP/(TP+FP)`、`recall = TP/(TP+FN)`；真值为该类但系统**拒判或执行失败**的样本计入该类 FN，不从分母移除。

| 标签 | 真实样本数 | 预测数 | TP | FP | FN | precision | recall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 支持 | 9 | 8 | 8 | 0 | 1 | 1.00 | 0.89 |
| 部分支持 | 4 | 5 | 3 | 2 | 1 | 0.60 | 0.75 |
| 相矛盾（单列） | 6 | 7 | 6 | 1 | 0 | 0.86 | 1.00 |
| 证据不足 | 5 | 4 | 3 | 1 | 2 | 0.75 | 0.60 |

**证据冲突识别率**（相矛盾类 recall）= 1.00；分子分母都来自本次真实运行，不是回放。

## 4. macro-F1（真值可判定三类，等权）

| 类别 | F1 |
| --- | --- |
| 支持 | 0.94 |
| 部分支持 | 0.67 |
| 相矛盾 | 0.92 |
| **macro-F1** | **0.84** |

参与平均的类别：支持、部分支持、相矛盾。

## 5. 应拒判样本上的错误确定判断率

R 为独立标注（签核）为证据不足的样本集合，不按系统输出倒推。

| 项目 | 值 |
| --- | --- |
| R 总数 | 5 |
| R 中 COMPLETED | 5 |
| R 中输出确定判断（错误确定判断） | 2 |
| 错误确定判断率（/ COMPLETED） | 0.40 |
| 全批次发生率（/ R 总数） | 0.40 |

误判（真值可判定却判成别的确定标签）：`PMC13648980-c01`。
过度拒判（真值可判定却判成证据不足）：`PMC13648980-c04`。

## 6. 逐条结果

| case | 期望标签 | 实际标签 | 标签来源 | 终态 | 错误码 | 发布引文（定位/总数） | 用时 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `PMC1182327-c01` | 支持 | 支持 | 模型判定 | COMPLETED | — | 2/2 | 12.1s |
| `PMC1182327-c02` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1/1 | 5.8s |
| `PMC1182327-c03` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1/1 | 8.8s |
| `PMC1182327-c04` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1/1 | 5.8s |
| `PMC1182327-c05` | 部分支持 | 部分支持 | 模型判定 | COMPLETED | — | 1/1 | 7.0s |
| `PMC1182327-c06` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1/1 | 5.4s |
| `PMC13648980-c01` | 支持 | 部分支持 | 模型判定 | COMPLETED | — | 2/2 | 14.5s |
| `PMC13648980-c02` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1/1 | 9.4s |
| `PMC13648980-c03` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 2/2 | 7.7s |
| `PMC13648980-c04` | 部分支持 | 证据不足 | 模型判定 | COMPLETED | — | 2/2 | 18.8s |
| `PMC13648980-c05` | 证据不足 | 相矛盾 | 模型判定 | COMPLETED | — | 2/2 | 8.4s |
| `PMC13648980-c06` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1/1 | 9.4s |
| `PMC13648980-c07` | 证据不足 | 证据不足 | 模型判定 | COMPLETED | — | 2/2 | 12.3s |
| `PMC13648980-c08` | 部分支持 | 部分支持 | 模型判定 | COMPLETED | — | 2/2 | 8.3s |
| `PMC7461750-c01` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1/1 | 6.4s |
| `PMC7461750-c02` | 证据不足 | 证据不足 | 模型判定 | COMPLETED | — | 0/0 | 4.4s |
| `PMC7461750-c03` | 证据不足 | 证据不足 | 模型判定 | COMPLETED | — | 0/0 | 6.5s |
| `PMC8806060-c01` | 支持 | 支持 | 模型判定 | COMPLETED | — | 2/2 | 7.1s |
| `PMC8806060-c02` | 支持 | 支持 | 模型判定 | COMPLETED | — | 2/2 | 7.6s |
| `PMC8806060-c03` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1/1 | 6.1s |
| `PMC8806060-c04` | 部分支持 | 部分支持 | 模型判定 | COMPLETED | — | 2/2 | 9.8s |
| `PMC8806060-c05` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1/1 | 6.9s |
| `PMC8806060-c06` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1/1 | 10.8s |
| `PMC8806060-c07` | 证据不足 | 部分支持 | 模型判定 | COMPLETED | — | 3/3 | 8.1s |

| 汇总 | 值 |
| --- | --- |
| 标签与人工答案一致 | **20 / 24** |
| 其中由**工作流降级**产出（不是模型判断） | 0 |

## 7. 原始输出（每次模型调用）

保留原始输出是为了定位：只剩一句错误码时无法判断是模型判错还是输出形状不合契约。

### `PMC1182327-c01` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["most published research findings are false","majority of published research findings are false","most published findings are false","published research findings are false","most research findings are wrong","false published research findings","majority of published findings are wrong"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选片段明确表述大多数当前已发表的研究发现为假，并称多数声称的研究发现是假的，与论断一致。","supported_parts":["大多数已发表的研究发现是错的"],"scope_differences":[],"limitations":["证据主要限定在当前/现代研究语境，未穷尽所有学科与历史时期"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"There is increasing concern that most current published research findings are false."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:2","quote":"It can be proven that most claimed research findings are false."}]}}
```

</details>

### `PMC1182327-c02` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries": ["smaller sample size research field lower probability findings true", "small sample size lower likelihood research findings true", "research field sample size probability findings true", "smaller research field findings less likely true", "sample size research field true findings probability"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文 Corollary 1 明确表述：科学领域中进行的研究越小，研究发现为真的可能性越低；随后说明小样本量意味着较低统计功效，而较低功效会使 PPV 下降，与论断对象、方向和范围一致。","supported_parts":["研究领域的样本量越小，其研究发现为真的可能性越低。"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:14","quote":"Corollary 1: The smaller the studies conducted in a scientific field, the less likely the research findings are to be true."}]}}
```

</details>

### `PMC1182327-c03` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries": ["flexibility in research design definitions outcomes and analysis", "researcher degrees of freedom false positive findings", "analytic flexibility lower likelihood findings are true", "flexible research methods increase false discoveries", "research design flexibility and reproducibility", "outcome definition flexibility and analysis flexibility", "greater flexibility research findings less likely true"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选片段明确给出与论断同义的推论：科学领域内设计、定义、结局和分析方式的灵活性越大，研究发现为真的可能性越低。","supported_parts":["研究设计、定义、结局与分析方式的灵活性越大，研究发现为真的可能性越低"],"scope_differences":[],"limitations":["证据为科学领域层面的理论框架/模拟推论，并非针对所有领域的系统实证汇总"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:17","quote":"Corollary 4: The greater the flexibility in designs, definitions, outcomes, and analytical modes in a scientific field, the less likely the research findings are to be true."}]}}
```

</details>

### `PMC1182327-c04` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["selective outcome reporting randomized controlled trials","outcome reporting bias randomized controlled trials","no selective outcome reporting randomized controlled trials","absence of selective outcome reporting randomized controlled trials","randomized controlled trials selective outcome reporting","selective outcome reporting in randomized trials"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确指出，即使在随机对照试验中，选择性结局报告（包括操纵所报告结局和分析）也是常见问题；这与论断“随机对照试验中不会出现选择性结局报告”的绝对否定表述相反。","supported_parts":[],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:17","quote":"there is strong evidence that selective outcome reporting, with manipulation of the outcomes and analyses reported, is a common problem even for randomized trails [25]."}]}}
```

</details>

### `PMC1182327-c05` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["randomized controlled trials conclusions 85 percent true","randomized controlled trial conclusions approximately 85 percent true","85 percent of randomized controlled trial conclusions are true","RCT conclusions 85 percent true","randomized trials conclusions true 85 percent","randomized controlled trials 85 percent true","conclusions of randomized controlled trials are true","randomized controlled trial results 85 percent true"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"证据中的85%仅适用于设计良好、有足够把握度且研究前对干预有效性有50%先验把握的随机对照试验，而论断将所有随机对照试验的结论概括为约85%为真，范围明显更宽。","supported_parts":["在预先有50%把握认为干预有效的前提下，设计良好、有足够把握度的随机对照试验的结论约有85%为真"],"scope_differences":["证据限定了随机对照试验的质量、把握度和50%研究前先验概率，论断未限定这些条件而泛化到随机对照试验的结论"],"limitations":["无法据此判定所有随机对照试验结论总体约有85%为真"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:21","quote":"A finding from a well-conducted, adequately powered randomized controlled trial starting with a 50% pre-study chance that the intervention is effective is eventually true about 85% of the time."}]}}
```

</details>

### `PMC1182327-c06` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries": ["peer review suppression of contrary findings", "prominent researchers suppress refuting research", "peer review gatekeeping against dissenting evidence", "scientific peer review bias contrary conclusions", "researchers unable to suppress refuting studies", "peer review and suppression of scientific disagreement"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确指出知名研究者可能通过同行评审压制反驳其结论的研究发表与传播，与论断“无法通过同行评审压制”在对应条件下方向相反。","supported_parts":[],"scope_differences":[],"limitations":["证据使用“may”表示可能性，并非断言所有知名研究者都会压制；但足以否定“无法压制”的绝对论断。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:18","quote":"Prestigious investigators may suppress via the peer review process the appearance and dissemination of findings that refute their findings"}]}}
```

</details>

### `PMC13648980-c01` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["rPMS treatment duration pain intensity VAS","repetitive peripheral magnetic stimulation pain intensity VAS","both rPMS groups significantly reduced pain VAS","4 week intervention rPMS VAS pain","rPMS four weeks pain intensity","treatment duration rPMS frozen shoulder VAS","significant reduction pain intensity VAS rPMS","rPMS protocols pain VAS four week intervention"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"候选片段显示10分钟和15分钟两种rPMS方案在4周内均出现VAS显著下降，但两组均同时接受标准化牵伸训练且无假刺激对照，原文明确不能据此确认rPMS本身的独立疗效，故为部分支持。","supported_parts":["两种rPMS方案（10分钟与15分钟，每周1次，共4周）在4周干预期内VAS均随时间显著改善。","第4周VAS较基线分别下降4.87分和5.02分。"],"scope_differences":["证据中的两种方案均同时接受标准化牵伸训练，无法将VAS下降单独归因于rPMS治疗时长。","证据来自单中心、特定上斜方肌肌筋膜疼痛综合征人群，外推范围有限。"],"limitations":["未设假刺激对照组，不能判定rPMS本身的独立镇痛疗效。","研究未设计或把握度检验等效性/非劣效性，不能据此确认两种时长的正式等效性。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:3","quote":"LMMs demonstrated significant improvements over time in VAS, PPT, and NDI (all p < 0.001), with no significant group-by-time interactions. At the prespecified primary endpoint (week 4), VAS decreased from baseline by 4.87 points in Protocol A and 5.02 points in Protocol B."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","quote":"because both groups received active rPMS combined with standardized stretching exercises, the present findings should be interpreted as a comparison between two active treatment protocols rather than as evidence confirming the efficacy of rPMS itself."}]}}
```

</details>

### `PMC13648980-c02` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["VAS score decreased 3.02 points at week 2","VAS score decreased 4.87 points at week 4","VAS reduction from baseline week 2 3.02 points","VAS reduction from baseline week 4 4.87 points","visual analogue scale baseline week 2 week 4 reduction","VAS scores baseline week 2 week 4","VAS continuously decreased during intervention","VAS decrease 3.02 4.87 baseline"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"证据明确报告与基线相比 VAS 在第2周下降3.02分、第4周下降4.87分，并报告显著时间主效应，支持干预期内持续下降。","supported_parts":["VAS在干预期内持续下降","第2周较基线降低3.02分","第4周降低4.87分"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:34","quote":"Compared with baseline, VAS decreased by 3.02 points at week 2 (95% CI −3.52 – −2.52; p < 0.001) and by 4.87 points at week 4 (95% CI −5.39 to −4.34; p < 0.001)"}]}}
```

</details>

### `PMC13648980-c03` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["15 minute rPMS more effective than 10 minute rPMS","rPMS 15 minutes versus 10 minutes efficacy","repetitive peripheral magnetic stimulation 15 minutes 10 minutes effectiveness","15-minute rPMS compared with 10-minute rPMS","ten minute rPMS versus fifteen minute rPMS treatment effect"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确报告15分钟与10分钟rPMS组在所有结局上无显著组×时间交互，恢复轨迹相当，并指出延长疗程未必成比例增强疗效；这与“15分钟方案比10分钟方案更有效”的论断方向相反。","supported_parts":[],"scope_differences":["证据限于慢性上斜方肌肌筋膜疼痛综合征成人、每周1次共4周且两组均联合标准化拉伸的患者；论断未限定这些条件。"],"limitations":["不能外推到其他rPMS参数、其他疾病人群或单独rPMS（未联合拉伸）的情境。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","quote":"no significant group-by-time interaction was observed for any outcome, suggesting that both stimulation durations produced comparable recovery trajectories."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:47","quote":"extending rPMS session duration may not proportionally enhance clinical outcomes"}]}}
```

</details>

### `PMC13648980-c04` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["10 minute regimen numerically better than 15 minute regimen","ten minute protocol superior to fifteen minute protocol","10 min versus 15 min numerical outcomes","ten minute schedule better than fifteen minute schedule","10 minute intervention numerically superior","15 minute intervention comparison numerical benefit","10 min protocol versus 15 min protocol results","numerical improvement with 10 minutes compared with 15 minutes"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"证据不足","rationale":"候选片段仅报告两组无显著组间差异和恢复轨迹相近，未提供 10 分钟与 15 分钟方案的具体数值或数值方向，因此无法核验“10 分钟在数值上优于 15 分钟”。","supported_parts":[],"scope_differences":["候选证据关注统计显著性和轨迹可比性，论断关注数值优劣方向。"],"limitations":["缺少 Table 3/4 的调整边际均值或组间数值对比，无法判定 10 分钟方案是否在数值上更优。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","quote":"both stimulation durations produced comparable recovery trajectories"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:41","quote":"no significant differences between groups at any visit"}]}}
```

</details>

### `PMC13648980-c05` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["rPMS stimulation clinical improvement","repetitive peripheral magnetic stimulation clinical improvement","rPMS stimulation itself","concurrent stretching exercises","stretching exercises placebo effect","rPMS versus stretching exercise","rPMS placebo controlled trial","frozen shoulder rPMS clinical improvement"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确指出，两组均接受 active rPMS 联合标准化拉伸练习，因而无法确定 rPMS 对观察到的临床改善的独立贡献，也无法将其与拉伸练习或情境/安慰效应区分；并说明本研究不能被解释为证实 rPMS 本身疗效的证据。该表述与论断相反。","supported_parts":[],"scope_differences":[],"limitations":["原文说明无法分离 rPMS、同期拉伸练习及情境/安慰效应，故不能将观察到的临床改善归因于 rPMS 刺激本身。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:49","quote":"Because both groups received active rPMS in combination with standardized stretching exercises, the independent contribution of rPMS to the observed clinical improvements could not be determined. Consequently, the specific effects of rPMS cannot be distinguished from the effects of stretching exercises or potential contextual and placebo-related influences."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:42","quote":"the present findings should be interpreted as a comparison between two active treatment protocols rather than as evidence confirming the efficacy of rPMS itself."}]}}
```

</details>

### `PMC13648980-c06` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["15-minute rPMS protocol","10-minute rPMS protocol","rPMS efficacy equivalence","therapeutic equivalence of rPMS protocols","15-minute versus 10-minute rPMS","rPMS treatment duration","repetitive peripheral magnetic stimulation protocols","equivalent efficacy of rPMS"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"原文明确说明研究未按等效性或非劣效性设计及把握度计算，未预设等效界值，并明确称组间无显著差异不应解释为正式的等效性证据；因此论断“证明了疗效等效”与原文相反。","supported_parts":["研究比较了15分钟与10分钟两种rPMS方案"],"scope_differences":[],"limitations":["原文仅报告未检测到显著组间差异，并明确不足以证明正式等效；无法支持“证明了疗效等效”。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:49","quote":"the study was not designed or powered as an equivalence or noninferiority trial and did not prespecify an equivalence or noninferiority margin. Therefore, the absence of significant between-group differences should not be interpreted as formal evidence of equivalence between treatment durations [52]."}]}}
```

</details>

### `PMC13648980-c07` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["rPMS clinical efficacy long term maintenance","repetitive peripheral magnetic stimulation long term efficacy","rPMS four week intervention follow up","clinical benefits maintained after four weeks rPMS","long term effects after four week rPMS treatment","rPMS treatment four weeks sustained improvement","repetitive peripheral magnetic stimulation four week intervention outcomes","rPMS follow up after intervention","clinical efficacy maintained at follow up rPMS","long term maintenance of rPMS clinical effects"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"证据不足","rationale":"候选片段仅报告至第4周的短期改善，并明确指出随访仅限4周、超过1个月的治疗效果耐久性仍不确定；未提供4周干预结束后长期维持疗效的可核查证据。","supported_parts":[],"scope_differences":["证据范围仅覆盖4周干预期/短期结局，未覆盖干预结束后超过1个月的长期随访。"],"limitations":["无法判定rPMS临床疗效在4周干预结束后能否长期维持；作者明确将超过1个月的耐久性列为不确定，并呼吁延长随访。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:49","quote":"follow-up was limited to 4 weeks; therefore, the durability of treatment effects beyond one month remains uncertain despite favourable short-term outcomes [28,29]."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:50","quote":"Future sham-controlled studies with longer follow-up are warranted to determine the specific therapeutic contribution of rPMS, establish optimal stimulation parameters, and evaluate the durability of treatment effects."}]}}
```

</details>

### `PMC13648980-c08` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["rPMS chronic neck pain effectiveness","repetitive peripheral magnetic stimulation chronic neck pain","rPMS efficacy in chronic neck pain patients","repetitive peripheral magnetic stimulation neck pain treatment","peripheral magnetic stimulation chronic cervical pain","rPMS generally effective chronic neck pain"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"证据支持 rPMS 对部分慢性颈痛相关人群（上斜方肌肌筋膜疼痛综合征）具有短期镇痛和改善颈部功能障碍的作用，但不足以支持“对慢性颈痛患者普遍有效”这一广泛结论。","supported_parts":["rPMS 对部分慢性颈痛相关人群（上斜方肌肌筋膜疼痛综合征患者）有效","rPMS 可降低疼痛强度并改善颈相关功能障碍"],"scope_differences":["论断覆盖“慢性颈痛患者”这一广泛人群，证据主要集中于上斜方肌肌筋膜疼痛综合征患者","证据涉及单次 10 分钟 rPMS 的短期效果，不能支持普遍或长期有效"],"limitations":["无法判定 rPMS 对其他类型慢性颈痛患者是否普遍有效","无法判定 rPMS 对全部慢性颈痛患者的普遍疗效或长期疗效"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:9","quote":"In upper trapezius MPS specifically, randomized sham-controlled evidence showed that a single 10-minute rPMS session significantly reduced pain intensity and improved neck-related disability"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:43","quote":"The findings are consistent with previous studies demonstrating analgesic and functional benefits of rPMS in musculoskeletal pain conditions"}]}}
```

</details>

### `PMC7461750-c01` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries": ["correction notice Fuchs KoCo19", "Dr Fuchs KoCo19 collaboration", "Fuchs omitted from KoCo19 authorship", "original publication omitted Fuchs", "Fuchs missing from author list", "KoCo19 collaboration author list", "correction to original publication authorship", "Fuchs KoCo19 author omission", "omitted authorship KoCo19 collaboration", "correction notice author omission"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选片段明确说明 Dr. Fuchs 在原发表文献中被错误遗漏为 KoCo19 合作组成员，与论断一致。","supported_parts":["原发表文献遗漏了 Fuchs 博士在 KoCo19 合作组中的署名"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:3","quote":"In the publication of the original article [1], the author Dr. Fuchs was erroneously omitted as a collaborator from the KoCo19 collaboration group."}]}}
```

</details>

### `PMC7461750-c02` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["cohort study recruited approximately 3000 participants in Munich","Munich cohort study 3000 participants","recruited about 3000 participants Munich","study participants recruited in Munich cohort","Munich recruitment cohort participants","FROZEN cohort Munich participants"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"证据不足","rationale":"候选片段仅说明原文勘误中遗漏了 Fuchs 博士作为 KoCo19 合作组成员，未提供该队列研究的招募地点或参与人数信息，无法核验“在慕尼黑招募约 3 000 名参与者”的论断。","supported_parts":[],"scope_differences":[],"limitations":["候选片段未涉及研究招募地点。","候选片段未涉及参与者人数。"],"evidence":[]}}
```

</details>

### `PMC7461750-c03` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries": ["follow-up completed between April and June 2020", "follow-up conducted between April and June 2020", "follow-up data collection April to June 2020", "study follow-up April 2020 June 2020", "follow-up period April June 2020"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"证据不足","rationale":"候选片段仅为更正声明和出版商致歉，未提及该研究的随访时间安排，无法核验论断。","supported_parts":[],"scope_differences":[],"limitations":["候选片段没有提供研究随访时间、方法或结果信息"],"evidence":[]}}
```

</details>

### `PMC8806060-c01` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["DF-Tiny-YOLO","DF-Tiny-YOLO apple leaf dataset","apple leaf dataset four classes","mean average precision apple leaf","mAP 99.99","DF-Tiny-YOLO mean average precision","DF-Tiny-YOLO mAP 99.99"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文在摘要和 3.2 实验结果中明确报告 DF-Tiny-YOLO 的 mAP 为 99.99%，且实验使用四类常见苹果叶图像数据，与论断的对象、指标和数值一致。","supported_parts":["DF-Tiny-YOLO 的 mAP 为 99.99%","实验数据包含四类苹果叶图像"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The results showed that the mean average precision (mAP) and average intersection over union (IoU) of the DF-Tiny-YOLO model were 99.99% and 90.88%, respectively"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:39","quote":"The mAP of DF-Tiny-YOLO is 99.99%, which was 0.17% higher than that of Tiny-YOLO."}]}}
```

</details>

### `PMC8806060-c02` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["DF-Tiny-YOLO 1x1 1x1 3x3 convolution kernels","DF-Tiny-YOLO end of network convolution kernel sequence","1x1 1x1 3x3 convolution improve detection accuracy","convolution kernels detection accuracy without increasing computational complexity","DF-Tiny-YOLO lightweight detection accuracy computational cost"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文明确说明 DF-Tiny-YOLO 在网络末端依次使用 1×1、1×1、3×3 卷积核，并指出其可在不增加计算复杂度的情况下提升检测精度，与论断的对象、条件和目的均一致。","supported_parts":["DF-Tiny-YOLO 在网络末端依次使用 1×1、1×1、3×3 卷积核","目的是在不增加计算复杂度的前提下提升检测精度"],"scope_differences":[],"limitations":["原文为方法描述，未提供该卷积排列相对于其他排列的消融实验数据；但这不影响对所述设计目的的支持。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:21","quote":"Using 1 × 1, 1 × 1, and 3 × 3 convolution kernels at the network terminals will contribute to reducing the dimension of features and increasing the network depth without increasing computational complexity, thus further improving the detection accuracy."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The network terminal uses convolution kernels of 1 × 1, 1 × 1, and 3 × 3, in turn, to realize the dimensionality reduction of features and increase network depth without increasing computational complexity, thus further improving the detection accuracy."}]}}
```

</details>

### `PMC8806060-c03` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries": ["1,404 images training test split", "1404 images randomly divided training test sets", "80 20 training test split", "80 percent training 20 percent testing", "randomly divided into training and test sets"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文明确说明数据共 1,404 张图像，并按 80%:20% 的比例随机划分为训练集与测试集，与论断一致。","supported_parts":["1,404 张图像按 80%:20% 的比例随机划分为训练集与测试集"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:23","quote":"total 1,404 images. Fig 4 describes the basic situation of four types of leaves. The images were randomly divided into training and test sets at a ratio of 80%:20%"}]}}
```

</details>

### `PMC8806060-c04` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["DF-Tiny-YOLO detection accuracy improvement over Tiny-YOLO","DF-Tiny-YOLO detection speed improvement over Tiny-YOLO","DF-Tiny-YOLO compared with original Tiny-YOLO","DF-Tiny-YOLO performance detection accuracy detection speed","original Tiny-YOLO benchmark DF-Tiny-YOLO"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"证据支持DF-Tiny-YOLO相对原始Tiny-YOLO在检测精度上有提升，但检测速度与原始Tiny-YOLO相同，并未提升，因此论断仅部分成立。","supported_parts":["DF-Tiny-YOLO相对原始Tiny-YOLO在检测精度上有提升"],"scope_differences":[],"limitations":["检测速度与原始Tiny-YOLO相同（280 FPS），未体现速度提升，故“检测速度有提升”不被支持。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:39","quote":"The mAP of DF-Tiny-YOLO is 99.99%, which was 0.17% higher than that of Tiny-YOLO."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:39","quote":"The detection speed was 280 FPS, which was the same as that of Tiny-YOLO"}]}}
```

</details>

### `PMC8806060-c05` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries": ["DF-Tiny-YOLO recall YOLOv2", "DF-Tiny-YOLO significantly higher recall", "DF-Tiny-YOLO recall comparison", "recall of DF-Tiny-YOLO versus YOLOv2", "DF-Tiny-YOLO YOLOv2 recall performance"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确报告 DF-Tiny-YOLO 的 Recall 为 1.00，并与 YOLOv2 相同，而非显著高于 YOLOv2。","supported_parts":[],"scope_differences":[],"limitations":["证据仅针对该文苹果叶病害检测实验的 Table 5 比较结果。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:39","quote":"Recall was 1.00, which was the same as YOLOV2 and 0.01 higher than Tiny-YOLO."}]}}
```

</details>

### `PMC8806060-c06` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries":["DF-Tiny-YOLO four classes consistent performance","DF-Tiny-YOLO recognition performance four categories","DF-Tiny-YOLO consistent across four classes","DF-Tiny-YOLO four category recognition results","DF-Tiny-YOLO class-wise performance consistency"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"原文明确称 DF-Tiny-YOLO 对 Apple cedar rust 和 healthy leaves 表现最佳，说明四个类别上的表现并不一致；这与论断“四个类别上的识别表现一致”相反。","supported_parts":[],"scope_differences":[],"limitations":["证据仅明确指出两类表现最佳，未列出四个类别的全部逐类指标。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:40","quote":"the model performs best for Apple cedar rust and healthy leaves."}]}}
```

</details>

### `PMC8806060-c07` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、解析通过</summary>

```text
{"queries": ["DF-Tiny-YOLO outperforms mainstream detection models", "DF-Tiny-YOLO comparison with three detection models", "DF-Tiny-YOLO superior detection performance", "DF-Tiny-YOLO comparative experiments detection models", "DF-Tiny-YOLO accuracy comparison baseline models"]}
```

</details>

<details><summary>第 2 次：purpose=decision、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"证据支持 DF-Tiny-YOLO 相比 YOLOv2 和 Tiny-YOLO 两个模型表现更优，但未支持其与三个及以上主流检测模型对比均更优；原文还明确难以与更多模型比较。","supported_parts":["DF-Tiny-YOLO 在实验对比中较 YOLOv2 和 Tiny-YOLO 表现更优"],"scope_differences":["论断要求与三个及以上主流检测模型对比，证据仅涵盖 YOLOv2 和 Tiny-YOLO 两个模型"],"limitations":["无法证明 DF-Tiny-YOLO 与三个及以上主流检测模型对比时均表现更优","原文说明受实验环境限制，难以与更多模型比较"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:45","quote":"among YOLOv2, Tiny-YOLO, the optimized DF-Tiny-YOLO network offered more advantages than the other two models"},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Compared with the Tiny-YOLO and YOLOv2 network models, the new method proposed in this paper significantly improves the detection performance."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:49","quote":"However, the study is limited by the experimental environment, which makes it difficult to compare with more models."}]}}
```

</details>

