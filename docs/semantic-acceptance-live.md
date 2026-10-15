# 真实模型语义验收记录（非门禁产物）

> 本文件由 `tests/functional/live_acceptance.py` 生成，**不参与 CI**，也**不逐字节可复现**。
> 它与 `docs/semantic-report.md` 分工不同：那一份由 `ScriptedGateway` 回放、逐字节可比对、由 CI 门禁；
> 这一份跑真实模型，因此每次输出的字节都可能不同，只能以「某日某模型的一次实测」被引用。

## 本次运行

| 项 | 值 |
| --- | --- |
| 生成时间 | 2026-10-15T19:47:24+08:00 |
| `PAPER_EVIDENCE_PROVIDER_MODEL` | `deepseek/deepseek-flash` |
| 上游回报的模型 | `deepseek-flash` |
| 冻结配置里的 `configured_model` | `agnes-2.5-flash`（**不是实际调用的模型**，见下） |
| 样本集 | `tests/functional/samples/`，N = 7 |
| 样本集指纹 | `sha256:08149557cc65b289` |
| 余额（前 → 后） | 3.90 → 3.87 |

复现命令（需网络与凭据，会真实计费）：

```bash
PAPER_EVIDENCE_PROVIDER_MODEL=<provider/model> \
PAPER_EVIDENCE_MODEL_API_KEY=<key> \
  python tests/functional/live_acceptance.py
```

## 这份记录不能被读成什么

- **不是可复现证据**。模型的输出不保证逐字节一致；引用时必须带上本文件顶部的生成时间与模型名。
- **不是 CI 门禁**。它不进 `.github/workflows/`，也不该进：CI 既无网络出口也无凭据。
- **不是「系统准确率」**。下游还要区分「模型判错」与「根本没产出标签」——见下表最后一列。
- **不是默认上游的表现**。产品默认上游与本次不同时，结论的可迁移性是有限的，须显式声明。

## 逐例结果

| case | 期望标签 | 实际标签 | 终态 | 错误码 | 证据条数 | 用时 |
| --- | --- | --- | --- | --- | --- | --- |
| `contradicted_causality` | 相矛盾 | **无标签** | FAILED | QUOTE_MISMATCH | — | 20.3s |
| `contradicted_negation` | 相矛盾 | **无标签** | FAILED | MODEL_INVALID_OUTPUT | — | 10.1s |
| `contradicted_object` | 相矛盾 | **无标签** | FAILED | MODEL_INVALID_OUTPUT | — | 11.7s |
| `insufficient_unrelated` | 证据不足 | 证据不足 | COMPLETED | RETRIEVAL_EMPTY | 0 | 8.9s |
| `partial_population_scope` | 部分支持 | **无标签** | FAILED | MODEL_INVALID_OUTPUT | — | 16.4s |
| `partial_quantity` | 部分支持 | **无标签** | FAILED | QUOTE_MISMATCH | — | 13.8s |
| `support_object_scope` | 支持 | 支持 | COMPLETED | — | 1 | 12.4s |

| 汇总 | 值 |
| --- | --- |
| 标签与人工核对一致 | **2 / 7** |
| **未产出标签**（`FAILED`/`BLOCKED` 等） | **5 / 7** |

> **5 例没有产出标签**，因此上面的「一致数」**不是准确率**：它没有把这些例计入任何一侧。
> 在产出标签之前，本记录不对语义准确率作任何结论。

## 原始输出（每次模型调用）

保留原始输出是为了定位：只剩一句错误码时无法判断是模型判错还是输出形状不合契约。

### `contradicted_causality` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment reduced mortality","mortality decreased after treatment","treatment lowered mortality","mortality reduction with treatment","frozen treatment mortality decrease","treatment effect on mortality"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"原文虽承认治疗后死亡率下降，但明确指出下降在治疗引入前两年已经开始，直接削弱并否定“该治疗导致死亡率下降”的因果归因。","supported_parts":["死亡率在治疗后下降（时间关联）"],"scope_differences":["原文支持治疗后下降的时间关联，但不支持治疗是下降原因；存在治疗前已开始的下降趋势。"],"limitations":["原文未提供多变量调整或因果推断，仅提示下降早于治疗，故不能完全排除治疗对后续下降有额外贡献。"],"evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Mortality fell after the treatment was introduced, but the decline had already begun two years earlier."}]}}
```

</details>

<details><summary>第 3 次：purpose=output_repair、repairs=contradicted_causality:decision:1、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"候选片段显示治疗引入后死亡率下降，提供了时间关联；但同时指出下降在治疗引入前两年已经开始，削弱了‘治疗导致死亡率下降’的因果归因。","supported_parts":["死亡率在治疗引入后下降，支持治疗与死亡率下降之间存在时间关联。"],"scope_differences":["论断主张治疗导致死亡率下降，属于因果结论；证据仅说明治疗引入后死亡率下降，且下降趋势早于治疗出现。"],"limitations":["存在治疗前已开始的下降趋势，无法排除其他因素或既有趋势导致死亡率下降。","仅凭该片段不能证明治疗与死亡率下降之间的因果关系。"],"evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Mortality fell after the treatment was introduced, but the decline had already begun two years earlier."}]}}
```

</details>

### `contradicted_negation` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries": ["significantly reduced mortality", "treatment significantly reduced mortality", "mortality was significantly lower", "reduced mortality rate", "lower mortality in treatment group", "decreased risk of death", "mortality benefit of treatment", "improved survival rate", "survival benefit treatment", "all cause mortality", "overall survival", "hazard ratio for mortality"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析失败</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明该治疗与安慰剂相比未降低死亡率，与论断“显著降低了死亡率”方向相反。","supported_parts":[],"scope_differences":"论断声称死亡率显著降低；候选原文仅报告未降低死亡率，未显示显著降低。","limitations":"候选片段未提供效应量、置信区间或具体死亡率数据，但足以与论断方向相矛盾。","evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment did not reduce mortality compared with placebo."}]}}
```

解析器判定：`OutputError: 动作字段不合法`

</details>

<details><summary>第 3 次：purpose=output_repair、repairs=contradicted_negation:decision:0、解析失败</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明该治疗与安慰剂相比并未降低死亡率，与论断“显著降低了死亡率”方向相反。","supported_parts":[],"scope_differences":"原文涉及与安慰剂比较的死亡率结果，但结论是未降低，而非显著降低。","limitations":"候选片段未提供效应量、置信区间或显著性检验细节。","evidence":[{"paragraph_id":"[p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1]","quote":"The treatment did not reduce mortality compared with placebo."}]}}
```

解析器判定：`OutputError: 动作字段不合法`

</details>

### `contradicted_object` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["Drug B reduce mortality","Drug B reduced mortality","Drug B lowers mortality","Drug B decreased mortality","Drug B mortality reduction","Drug B survival benefit","Drug B all cause mortality","Drug B death rate","Drug B mortality outcome","Drug B risk of death"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析失败</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明 Drug B 没有可测量的效果，与“Drug B 能降低死亡率”的论断直接冲突。","supported_parts":[],"scope_differences":[],"limitations":"证据仅来自该候选片段中的一句结果描述，但足以否定 Drug B 降低死亡率的说法。","evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Drug A reduced mortality, whereas Drug B had no measurable effect."}]}}
```

解析器判定：`OutputError: 动作字段不合法`

</details>

<details><summary>第 3 次：purpose=output_repair、repairs=contradicted_object:decision:0、解析失败</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明 Drug B 没有可测量的效果，而论断称 Drug B 能降低死亡率，两者方向相反。","supported_parts":[],"scope_differences":"无。","limitations":"该证据来自单一结果句，未提供额外统计细节。","evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Drug A reduced mortality, whereas Drug B had no measurable effect."}]}}
```

解析器判定：`OutputError: 动作字段不合法`

</details>

### `insufficient_unrelated` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["frozen treatment reduced mortality by 20%","frozen treatment mortality reduction 20%","frozen lowered mortality by 20 percent","treatment reduced mortality by 20%","mortality reduced by 20%","20% reduction in mortality","mortality reduction of 20%","treatment lowered mortality by 20 percent","frozen mortality reduction"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"retrieve","queries":["该治疗把死亡率降低了 20%","treatment reduced mortality by 20%","mortality reduction 20% treatment"],"neighbor_paragraph_ids":[]}
```

</details>

### `partial_population_scope` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries": ["treatment reduced mortality in all age groups", "mortality reduction across all age groups", "treatment lower mortality all ages", "age group mortality reduction treatment", "reduced death rates all age groups"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选片段显示治疗仅降低了成人死亡率，而儿童死亡率未发生变化；因此“所有年龄组的死亡率降低”这一全称论断与证据不一致。","supported_parts":["成人的死亡率降低了20%。"],"scope_differences":["论断声称所有年龄组死亡率降低；证据仅支持成人死亡率降低，并显示儿童死亡率未变。"],"limitations":["候选片段只涉及成人与儿童，未覆盖其他年龄组。"],"evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"In adults, the treatment reduced mortality by 20 percent."},{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:2","quote":"Mortality in children was unchanged."}]}}
```

</details>

<details><summary>第 3 次：purpose=output_repair、repairs=partial_population_scope:decision:1、解析失败</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选片段显示成人死亡率降低20%，但儿童死亡率未改变；因此不能支持‘所有年龄组’死亡率降低，儿童结果直接反驳全年龄组均降低。","supported_parts":["成人死亡率降低20%"],"scope_differences":"论断范围为所有年龄组；证据仅涉及成人和儿童，并显示儿童无改善。","limitations":"候选片段未列出全部年龄组，但已足以反驳‘所有年龄组均降低’。","evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"In adults, the treatment reduced mortality by 20 percent."},{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:2","quote":"Mortality in children was unchanged."}]}}
```

解析器判定：`OutputError: 动作字段不合法`

</details>

### `partial_quantity` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries": ["treatment reduced mortality by approximately 50 percent", "mortality reduced by about 50 percent", "50 percent reduction in mortality", "treatment mortality reduction 50 percent", "relative reduction in mortality 50 percent", "mortality risk reduced by half", "treatment decreased mortality by half", "mortality benefit treatment 50 percent", "hazard ratio mortality 0.50", "risk ratio mortality 0.5"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析失败</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文显示治疗使死亡率降低 20%，而论断称降低约 50%，两者在效应量上明显不一致。","supported_parts":[],"scope_differences":"论断的效应量约为 50%，候选原文为 20%。","limitations":"仅凭该候选片段无法判断不同人群、终点定义或统计模型是否会造成差异；但就给出的死亡率降低幅度而言，与论断不一致。","evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

解析器判定：`OutputError: 动作字段不合法`

</details>

<details><summary>第 3 次：purpose=output_repair、repairs=partial_quantity:decision:0、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确报告治疗使死亡率降低20%，而论断称降低约50%，两者数值不一致，构成矛盾。","supported_parts":[],"scope_differences":["原文降幅为20%，论断为约50%，效应量不一致"],"limitations":["仅依据单个结果句，未提供置信区间或绝对风险信息"],"evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

</details>

### `support_object_scope` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment reduced mortality by 20 percent","treatment reduced mortality by 20%","mortality reduced by 20 percent","mortality reduction of 20 percent","20 percent reduction in mortality","20% mortality reduction","treatment lowered mortality by 20 percent","mortality decrease 20 percent"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析失败</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文第1段直接报告治疗使死亡率降低了20%，与论断核心内容一致。","supported_parts":["治疗把死亡率降低了20%"],"scope_differences":"无明显范围差异。","limitations":"原文未提供置信区间、绝对风险降幅或统计显著性等附加信息，但核心数值与方向均有直接表述支持。","evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

解析器判定：`OutputError: 动作字段不合法`

</details>

<details><summary>第 3 次：purpose=output_repair、repairs=support_object_scope:decision:0、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文片段明确报告治疗使死亡率降低20%，与论断一致。","supported_parts":["治疗把死亡率降低了20%"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

</details>

