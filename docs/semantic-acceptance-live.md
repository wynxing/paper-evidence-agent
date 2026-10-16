# 真实模型语义验收记录（非门禁产物）

> 本文件由 `tests/functional/live_acceptance.py` 生成，**不参与 CI**，也**不逐字节可复现**。
> 它与 `docs/semantic-report.md` 分工不同：那一份由 `ScriptedGateway` 回放、逐字节可比对、由 CI 门禁；
> 这一份跑真实模型，因此每次输出的字节都可能不同，只能以「某日某模型的一次实测」被引用。

## 本次运行

| 项 | 值 |
| --- | --- |
| 生成时间 | 2026-10-16T08:53:26+08:00 |
| 运行所在提交 | `db006613354a3f84067521e8232fe52188a84182` |
| `PAPER_EVIDENCE_PROVIDER_MODEL` | `deepseek/deepseek-flash` |
| 上游回报的模型 | `deepseek-flash` |
| 冻结快照里的 `provider_model` | `deepseek/deepseek-flash`（本进程请求的名字；`#68` / `PR #75` 起进快照与 `config_digest`） |
| 冻结配置里的 `configured_model` | `agnes-2.5-flash`（**不是实际调用的模型**，见下） |
| 样本集 | `tests/functional/samples/`，N = 7 |
| 样本集指纹 | `sha256:08149557cc65b289` |
| 余额（前 → 后） | 3.70 → 3.70 |

复现命令（需网络与凭据，会真实计费）：

```bash
PAPER_EVIDENCE_PROVIDER_MODEL=<provider/model> \
PAPER_EVIDENCE_MODEL_API_KEY=<key> \
  python tests/functional/live_acceptance.py
```

## 这份记录不能被读成什么

- **不是可复现证据**。模型的输出不保证逐字节一致；引用时必须带上本文件顶部的生成时间与模型名。
- **不是 CI 门禁**。它不进 `.github/workflows/`，也不该进：CI 既无网络出口也无凭据。
- **不是「系统准确率」**。下游要分开看三件事：**没产出标签**、**标签由工作流降级产出**、**模型判错**。前两者都不是模型判断，不能计入任何一侧。
- **「标签来源」列里的「工作流降级」不是模型的判断**。有界检索为空时由 `graph/workflow.py` 自己返回 `INSUFFICIENT_EVIDENCE`（该行通常伴有 `RETRIEVAL_EMPTY`）。它可能正好与人工核对一致，但那是规则对了，不是模型对了。
- **不是默认上游的表现**。产品默认上游与本次不同时，结论的可迁移性是有限的，须显式声明。

## 逐例结果

| case | 期望标签 | 实际标签 | 标签来源 | 终态 | 错误码 | 证据条数 | 用时 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `contradicted_causality` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1 | 9.8s |
| `contradicted_negation` | 相矛盾 | **无标签** | — | FAILED | QUOTE_MISMATCH | — | 13.2s |
| `contradicted_object` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1 | 9.9s |
| `insufficient_unrelated` | 证据不足 | 证据不足 | 模型判定 | COMPLETED | — | 0 | 7.3s |
| `partial_population_scope` | 部分支持 | 相矛盾 | 模型判定 | COMPLETED | — | 2 | 6.4s |
| `partial_quantity` | 部分支持 | **无标签** | — | FAILED | QUOTE_MISMATCH | — | 16.3s |
| `support_object_scope` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1 | 8.5s |

| 汇总 | 值 |
| --- | --- |
| 标签与人工核对一致 | **4 / 7** |
| **未产出标签**（`FAILED`/`BLOCKED` 等） | **2 / 7** |
| 其中标签由**工作流降级**（不是模型判断）产出 | **0 / 7** |

> 余额前后读数相同，**不代表本次没有计费**：结算有延迟，按余额差估算花费并不可靠。

> **2 例没有产出标签**，因此上面的「一致数」**不是准确率**：它没有把这些例计入任何一侧。
> 在产出标签之前，本记录不对语义准确率作任何结论。

## 原始输出（每次模型调用）

保留原始输出是为了定位：只剩一句错误码时无法判断是模型判错还是输出形状不合契约。

### `contradicted_causality` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment decreased mortality","treatment reduced mortality","mortality reduction treatment","lower mortality treatment","decrease in mortality","reduced mortality","mortality decline","improved survival treatment","treatment mortality benefit","mortality rate decrease"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"片段虽承认治疗引入后死亡率下降，但明确指出下降在治疗引入前两年已经开始，直接削弱“该治疗导致了死亡率下降”的因果归因。","supported_parts":["死亡率在治疗引入后下降"],"scope_differences":[],"limitations":["片段未提供治疗是否额外加速或贡献于死亡率下降的进一步分析。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Mortality fell after the treatment was introduced, but the decline had already begun two years earlier."}]}}
```

</details>

### `contradicted_negation` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["significantly reduced mortality","treatment significantly reduced mortality","mortality was significantly reduced","significant reduction in mortality","reduced mortality rate","treatment reduced mortality","lower mortality in treatment group","frozen treatment mortality"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确报告治疗组与安慰剂组相比未降低死亡率，与论断“显著降低了死亡率”方向相反。","supported_parts":[],"scope_differences":[],"limitations":["候选片段未提供具体死亡率数值、置信区间或显著性检验结果，无法评估效应量。"] ,"evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment did not reduce mortality compared with placebo."}]}}
```

</details>

<details><summary>第 3 次：purpose=output_repair、repairs=contradicted_negation:decision:1、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确报告该治疗与安慰剂相比未降低死亡率，与‘该治疗显著降低了死亡率’的论断方向相反。","supported_parts":[],"scope_differences":[],"limitations":["原文未提供死亡率的统计显著性细节，但仍直接否定死亡率降低的结论。"],"evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment did not reduce mortality compared with placebo."}]}}
```

</details>

### `contradicted_object` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["Drug B reduces mortality","Drug B reduced mortality","Drug B lowers mortality","Drug B lowered mortality","Drug B decreases mortality","Drug B decreased mortality","Drug B mortality reduction","Drug B survival benefit","Drug B improved survival","Drug B risk of death","Drug B all-cause mortality","Drug B death rate","mortality reduction with Drug B","Drug B lower death rate"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明 Drug B 没有可测量的效果，而 Drug A 才降低死亡率；这与“Drug B 能降低死亡率”的论断相矛盾。","supported_parts":[],"scope_differences":[],"limitations":["候选片段未提供 Drug B 对死亡率影响的其他统计细节，但已明确其无可测量效果。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Drug B had no measurable effect"}]}}
```

</details>

### `insufficient_unrelated` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["mortality reduced by 20%","20% reduction in mortality","treatment reduced mortality by 20%","mortality decreased by 20%","20% lower mortality with treatment","treatment mortality reduction 20%","relative risk reduction mortality 20%","mortality rate reduced by 20 percent","FROZEN trial mortality reduction","FROZEN treatment mortality 20%"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"证据不足","rationale":"候选片段仅说明结果采用混合效应模型分析，未提及该治疗、死亡率或20%的降低幅度，无法支持或反驳该论断。","supported_parts":[],"scope_differences":[],"limitations":["候选片段没有提供治疗对死亡率影响的任何效应量、置信区间或统计结果。","无法判定死亡率是否降低20%。"],"evidence":[]}}
```

</details>

### `partial_population_scope` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment reduced mortality","mortality reduction all age groups","reduced mortality across age groups","all age groups mortality","lower mortality in all age groups","treatment effect on mortality","mortality all ages","age specific mortality reduction"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选片段显示该治疗仅降低了成人死亡率，而儿童死亡率未变化；因此“降低了所有年龄组的死亡率”与证据不符。","supported_parts":[],"scope_differences":["论断覆盖所有年龄组；证据仅分别提及成人和儿童，且儿童结果并未降低。"],"limitations":["无法判定除成人和儿童之外其他年龄组的情况。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"In adults, the treatment reduced mortality by 20 percent."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:2","quote":"Mortality in children was unchanged."}]}}
```

</details>

### `partial_quantity` 的 3 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment reduced mortality by about 50 percent","treatment reduced mortality by approximately 50 percent","mortality reduced by about 50 percent","mortality reduced by approximately 50 percent","mortality decreased by 50 percent","mortality rate reduced by half","treatment lowered mortality by half","50 percent reduction in mortality","fifty percent reduction in mortality","relative reduction in mortality 50 percent","mortality benefit 50 percent","treatment mortality 50 percent"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确称死亡率降低20%，与论断所称约50%在关键数值上不一致。","supported_parts":["该治疗降低了死亡率"],"scope_differences":[],"limitations":["原文仅给出20%的降幅，未说明约50%或可支持该数量级的区间。"],"evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

</details>

<details><summary>第 3 次：purpose=output_repair、repairs=partial_quantity:decision:1、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"原文报告该治疗使死亡率降低 20%，而论断称降低约 50%，二者数值明显不一致。","supported_parts":[],"scope_differences":[],"limitations":["原文未给出置信区间或绝对死亡率，但这不影响其对50%降幅的不支持。"],"evidence":[{"paragraph_id":"PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

</details>

### `support_object_scope` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries": ["treatment reduced mortality by 20%", "mortality reduced by 20%", "20% reduction in mortality", "treatment mortality reduction", "mortality rate reduction 20%", "reduced mortality 20%", "treatment effect on mortality", "mortality benefit 20%", "frozen trial mortality reduction", "frozen treatment mortality"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文片段明确报告治疗使死亡率降低了20%，与论断一致。","supported_parts":["该研究报告的治疗把死亡率降低了20%"],"scope_differences":[],"limitations":["仅能确认该片段直接陈述了此结果，未提供统计学显著性、置信区间或适用人群等细节。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

</details>

