# 真实模型语义验收记录（非门禁产物）

> 本文件由 `tests/functional/live_acceptance.py` 生成，**不参与 CI**，也**不逐字节可复现**。
> 它与 `docs/semantic-report.md` 分工不同：那一份由 `ScriptedGateway` 回放、逐字节可比对、由 CI 门禁；
> 这一份跑真实模型，因此每次输出的字节都可能不同，只能以「某日某模型的一次实测」被引用。

## 本次运行

| 项 | 值 |
| --- | --- |
| 生成时间 | 2026-10-21T22:34:08+08:00 |
| 运行所在提交 | `905042dc5be9f52752f46c8bcfc78e6b862a6525` |
| `PAPER_EVIDENCE_PROVIDER_MODEL` | `deepseek/deepseek-flash` |
| 上游回报的模型 | `deepseek-flash` |
| 冻结快照里的 `provider_model` | `deepseek/deepseek-flash`（本进程请求的名字；`#68` / `PR #75` 起进快照与 `config_digest`） |
| 冻结配置里的 `configured_model` | `agnes-2.5-flash`（**不是实际调用的模型**，见下） |
| 样本集 | `tests/functional/samples/`，N = 7 |
| 样本集指纹 | `sha256:08149557cc65b289` |
| 余额（前 → 后） | 15.33 → 15.33 |

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
| `contradicted_causality` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1 | 5.2s |
| `contradicted_negation` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1 | 5.4s |
| `contradicted_object` | 相矛盾 | 相矛盾 | 模型判定 | COMPLETED | — | 1 | 3.7s |
| `insufficient_unrelated` | 证据不足 | 证据不足 | 工作流降级 | COMPLETED | RETRIEVAL_EMPTY | 0 | 5.1s |
| `partial_population_scope` | 部分支持 | 相矛盾 | 模型判定 | COMPLETED | — | 2 | 6.5s |
| `partial_quantity` | 部分支持 | 部分支持 | 模型判定 | COMPLETED | — | 1 | 7.1s |
| `support_object_scope` | 支持 | 支持 | 模型判定 | COMPLETED | — | 1 | 4.4s |

| 汇总 | 值 |
| --- | --- |
| 标签与人工核对一致 | **6 / 7** |
| **未产出标签**（`FAILED`/`BLOCKED` 等） | **0 / 7** |
| 其中标签由**工作流降级**（不是模型判断）产出 | **1 / 7** |

> 余额前后读数相同，**不代表本次没有计费**：结算有延迟，按余额差估算花费并不可靠。

## 原始输出（每次模型调用）

保留原始输出是为了定位：只剩一句错误码时无法判断是模型判错还是输出形状不合契约。

### `contradicted_causality` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries": ["treatment reduced mortality", "decreased mortality", "mortality reduction", "lower mortality rate", "treatment mortality benefit", "reduction in death rate"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"证据承认治疗引入后死亡率下降，但明确指出下降在治疗引入前两年已经开始，直接否定“该治疗导致死亡率下降”的因果归因。","supported_parts":["死亡率出现了下降"],"scope_differences":[],"limitations":["证据针对该治疗引入前后的时间关系，不能据此推断所有其他情形。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Mortality fell after the treatment was introduced, but the decline had already begun two years earlier."}]}}
```

</details>

### `contradicted_negation` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries": ["treatment significantly reduced mortality", "significantly reduced mortality", "significant reduction in mortality", "mortality was significantly reduced", "treatment reduced mortality", "reduced mortality", "lower mortality", "mortality reduction"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明与安慰剂相比该治疗未降低死亡率，直接否定论断中“显著降低了死亡率”的表述。","supported_parts":[],"scope_differences":[],"limitations":["原文未给出具体死亡率数值或显著性统计量，但已明确否定降低死亡率。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment did not reduce mortality compared with placebo."}]}}
```

</details>

### `contradicted_object` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["Drug B reduce mortality","Drug B reduced mortality","Drug B lower mortality","Drug B decreased mortality","Drug B mortality reduction","Drug B mortality outcomes","Drug B survival benefit"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"候选原文明确说明 Drug B 没有可测量的效果，与“Drug B 能降低死亡率”的论断方向相反。","supported_parts":[],"scope_differences":[],"limitations":["原文仅涉及该研究结果中的死亡率表述，未提供具体数值或置信区间。"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"Drug B had no measurable effect."}]}}
```

</details>

### `insufficient_unrelated` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment reduced mortality by 20 percent","mortality reduced by 20 percent","20 percent reduction in mortality","treatment lowered mortality by 20 percent","mortality decreased by 20 percent","mortality reduction of 20 percent","treatment mortality reduction 20 percent","reduced mortality 20 percent"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"retrieve","queries":["治疗 死亡率 降低 20%","mortality rate reduced by 20% treatment"],"neighbor_paragraph_ids":[]}
```

</details>

### `partial_population_scope` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment reduced mortality in all age groups","reduced mortality across all age groups","lower mortality in every age group","mortality reduction in all age groups","treatment lowered mortality for all ages","mortality decreased across all age groups","all age groups showed reduced mortality","treatment effect on mortality by age group"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"相矛盾","rationale":"证据显示成人死亡率降低，但儿童死亡率未改变；因此“所有年龄组死亡率均降低”被明确否定。","supported_parts":["成人死亡率降低20%"],"scope_differences":["证据仅报告成人和儿童，未覆盖其他所有年龄组"],"limitations":["无法判定除成人和儿童之外的年龄组"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"In adults, the treatment reduced mortality by 20 percent."},{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:2","quote":"Mortality in children was unchanged."}]}}
```

</details>

### `partial_quantity` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment reduced mortality by approximately 50 percent","mortality was reduced by about 50 percent","death rate decreased by approximately 50 percent","treatment group mortality reduction 50 percent","frozen treatment mortality reduction"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"部分支持","rationale":"证据支持该治疗降低死亡率，但降幅为 20%，与论断所称约 50% 存在重要数量差异。","supported_parts":["该治疗降低了死亡率"],"scope_differences":["证据显示死亡率降低 20%，论断称降低约 50%"],"limitations":["无法支持约 50% 的降幅"],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

</details>

### `support_object_scope` 的 2 次调用

<details><summary>第 1 次：purpose=query_generation、repairs=None、解析通过</summary>

```text
{"queries":["treatment reduced mortality by 20 percent","mortality reduced by 20 percent","20 percent reduction in mortality","20 percent lower mortality","treatment mortality benefit 20 percent","reduced risk of death by 20 percent","mortality outcome treatment group","treatment effect on mortality"]}
```

</details>

<details><summary>第 2 次：purpose=decision、repairs=None、解析通过</summary>

```text
{"action":"final","decision":{"label":"支持","rationale":"候选片段明确报告治疗使死亡率降低20%，与论断的对象、方向和数量一致。","supported_parts":["该研究报告的治疗把死亡率降低了20%"],"scope_differences":[],"limitations":[],"evidence":[{"paragraph_id":"p:PMC0000001:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:jats-0.1.0:1","quote":"The treatment reduced mortality by 20 percent."}]}}
```

</details>

