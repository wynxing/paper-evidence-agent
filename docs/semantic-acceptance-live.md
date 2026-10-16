# 真实模型语义验收记录（非门禁产物）

> 本文件由 `tests/functional/live_acceptance.py` 生成，**不参与 CI**，也**不逐字节可复现**。
> 它与 `docs/semantic-report.md` 分工不同：那一份由 `ScriptedGateway` 回放、逐字节可比对、由 CI 门禁；
> 这一份跑真实模型，因此每次输出的字节都可能不同，只能以「某日某模型的一次实测」被引用。

## 本次运行

| 项 | 值 |
| --- | --- |
| 生成时间 | 2026-10-16T15:21:16+08:00 |
| 运行所在提交 | `bc696c6ccf751075f3892edb4d73a9e3703e7fad` |
| `PAPER_EVIDENCE_PROVIDER_MODEL` | `deepseek/deepseek-flash` |
| 上游回报的模型 | `deepseek-flash` |
| 冻结快照里的 `provider_model` | `deepseek/deepseek-flash`（本进程请求的名字；`#68` / `PR #75` 起进快照与 `config_digest`） |
| 冻结配置里的 `configured_model` | `agnes-2.5-flash`（**不是实际调用的模型**，见下） |
| 样本集 | `tests/functional/samples/`，N = 7 |
| 样本集指纹 | `sha256:08149557cc65b289` |
| 余额（前 → 后） | 3.66 → 3.66 |

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
| `contradicted_causality` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1 | 8.7s |
| `contradicted_negation` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1 | 5.0s |
| `contradicted_object` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1 | 14.0s |
| `insufficient_unrelated` | 证据不足 | 证据不足 | 模型判定 | COMPLETED | — | 0 | 11.0s |
| `partial_population_scope` | 部分支持 | 相矛盾 | 模型判定 | COMPLETED | — | 2 | 8.9s |
| `partial_quantity` | 部分支持 | 相矛盾 | 模型判定 | COMPLETED | — | 1 | 11.0s |
| `support_object_scope` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1 | 11.9s |

| 汇总 | 值 |
| --- | --- |
| 标签与人工核对一致 | **5 / 7** |
| **未产出标签**（`FAILED`/`BLOCKED` 等） | **0 / 7** |
| 其中标签由**工作流降级**（不是模型判断）产出 | **0 / 7** |

> 余额前后读数相同，**不代表本次没有计费**：结算有延迟，按余额差估算花费并不可靠。

## 原始输出（每次模型调用）

保留原始输出是为了定位：只剩一句错误码时无法判断是模型判错还是输出形状不合契约。

### `contradicted_causality` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries": ["treatment decreased mortality", "treatment reduced mortality", "lower mortality after treatment", "mortality reduction with treatment", "treatment associated with decreased mortality", "reduced death rate treatment"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"证据显示死亡率下降在治疗引入前两年已经开始，因此不能支持“该治疗导致死亡率下降”的因果论断，反而与该因果归因相矛盾。","supported_parts":["治疗后死亡率下降"],"scope_differences":[],"limitations":["原文只指出死亡率下降先于治疗引入，未提供其他能支持因果关系的证据。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Mortality fell after the treatment was introduced, but the decline had already begun two years earlier."}]}}
```

</details>

### `contradicted_negation` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment significantly reduced mortality","significantly reduced mortality","treatment reduced death rate","significant mortality reduction","lower mortality with treatment"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明该治疗与安慰剂相比并未降低死亡率，与论断“显著降低了死亡率”方向相反。","supported_parts":[],"scope_differences":[],"limitations":["候选片段未提供具体效应量、置信区间或显著性检验细节，但已足以否定“降低死亡率”的方向性结论。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment did not reduce mortality compared with placebo."}]}}
```

</details>

### `contradicted_object` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["Drug B mortality","Drug B reduce mortality","Drug B reduced mortality","Drug B decreased mortality","Drug B lower mortality","Drug B survival benefit","Drug B death rate","mortality reduction","reduced mortality"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明 Drug B 没有可测量的效果，而 Drug A 才降低死亡率，与论断“Drug B 能降低死亡率”直接相反。","supported_parts":[],"scope_differences":[],"limitations":["候选片段仅涉及死亡率这一结果，未提供其他结局或具体效应量信息。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Drug A reduced mortality, whereas Drug B had no measurable effect."}]}}
```

</details>

### `insufficient_unrelated` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries": ["treatment reduced mortality by 20 percent", "20 percent reduction in mortality", "mortality decreased by 20 percent with treatment", "treatment associated with 20 percent lower mortality", "twenty percent mortality reduction", "mortality rate reduced 20 percent", "frozen treatment mortality reduction 20 percent", "frozen 20 percent mortality decrease"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"证据不足","rationale":"候选片段仅说明使用混合效应模型进行数据分析，未提及任何治疗、死亡率或降低 20% 的结果，无法支持或反驳该论断。","supported_parts":[],"scope_differences":[],"limitations":["候选片段没有提供治疗、死亡率变化或 20% 降幅的相关信息。"],"evidence":[]}}
```

</details>

### `partial_population_scope` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment reduced mortality in all age groups","mortality reduction across all age groups","treatment lowered mortality all ages","all age groups mortality benefit","age specific mortality reduction treatment","reduced mortality in every age group","mortality decrease among all age groups","treatment effect on mortality by age group"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选证据显示治疗仅在成人中降低死亡率，而儿童死亡率未改变，因此与“所有年龄组死亡率均降低”的论断相矛盾。","supported_parts":["在成人中，该治疗使死亡率降低20%。"],"scope_differences":[],"limitations":["候选证据仅涉及成人和儿童，未覆盖其他年龄组。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"In adults, the treatment reduced mortality by 20 percent."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:2","quote":"Mortality in children was unchanged."}]}}
```

</details>

### `partial_quantity` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["mortality reduced by about 50%","treatment reduced mortality by approximately 50%","50% reduction in mortality","mortality rate decreased by 50%","mortality lowered by 50%","relative risk of mortality 0.50","hazard ratio for mortality 0.50","absolute mortality reduction 50%","treatment effect on mortality","mortality benefit 50%"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确给出治疗使死亡率降低 20%，与论断中的约 50% 直接不符。","supported_parts":[],"scope_differences":[],"limitations":["候选片段仅给出 20% 这一数值，未提供置信区间或其他修饰信息。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

</details>

### `support_object_scope` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["mortality reduced by 20 percent","20 percent reduction in mortality","treatment lowered mortality by 20 percent","20% reduction in mortality","mortality decreased by 20%","deaths reduced by 20 percent","relative reduction in mortality 20 percent","treatment effect on mortality","all cause mortality reduction","mortality benefit of treatment","risk of death reduced","mortality endpoint results","survival improvement treatment","frozen study mortality","frozen trial treatment"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选原文明确报告治疗使死亡率降低了 20%，与论断完全一致。","supported_parts":["该研究报告的治疗把死亡率降低了 20%"],"scope_differences":[],"limitations":["未提供置信区间、统计显著性或其他研究细节"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

</details>

