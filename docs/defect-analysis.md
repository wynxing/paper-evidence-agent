# 缺陷分析报告

**范围**：截至 2026-10-20，功能定型（`v0.3.0-test-freeze`）与之后的缺陷修复。逐轮验证流水在 [verification.md](verification.md)，真实模型的原始输出在 [semantic-acceptance-live.md](semantic-acceptance-live.md)；本文件只做**归因汇总**，不重复那两份的记录。

归因口径与 `tests/functional/triage.py` 的 code 一致：拿一份诊断包，机器能复算出「主因是哪一层、被排除了哪几层」。本报告里每条缺陷都写了复现命令，用于复核这个归因，而不是只读一段叙述。

## 这份报告能被读成什么，不能被读成什么

**能**：每条缺陷落在哪一层、判据错在哪里、修了什么、用什么命令能再看到一次。

**不能**：

- 不是**发生率**。真实模型证据是单上游（`deepseek/deepseek-flash`）、7 例构造样本、每次运行独立抽样。「3 / 3 同向」是观察，不是比率。
- 不是**准确率**。缺陷版本里大量用例根本没产出标签，既不算对也不算错。
- 不是「已全部验证」的清单。每条都标注了它是**结构性事实已修**，还是**在真实模型上复测过**。两者不是一回事。

## 归因层次

| 层 | 判据落点 | 条数 |
| --- | --- | --- |
| 来源层 | 取回、许可、记录身份 | 3 |
| 契约层 | 输出形状、ID 形状、顶层严格度 | 3 |
| 判据层 | 提示词有没有携带判据 | 1 |
| 账务层 | `request_id` 归属、`config_digest`、重试等待 | 3 |
| 方法层 | 测试替身把上游行为写死 | 2 |

一条缺陷归到哪层，看的是**修哪里能让症状消失**，不是看它在哪里被发现。下面每条都写了「为什么不是相邻那层」，因为错误码经常指错排查方向——这本身是这批缺陷里反复出现的形态。

---

## 来源层

### D-01 上游错误体随 HTTP 400 到达，回落分支一次都没执行（#61）

**现象**：非 OA 记录本应「先取 `pmc`、被拒后回落 `pmc_fm`」，真实运行时回落从未发生，记录直接 `FAILED / UPSTREAM_INVALID_REQUEST`。

**归因**：`sources/pmc.py::_get_record` 在解析响应体**之前**按状态码拒绝，而 PMC 把 `<error code="cannotDisseminateFormat">` 随 **HTTP 400** 返回（真实抽样 10 / 10 如此）。判据看的是「状态码是不是 200」，而协议说的是「错误体会说明原因」。

**为什么不是相邻那层**：错误码落在 `UPSTREAM_INVALID_REQUEST`，看起来像「我们发了非法请求」。实际请求合法，是响应体的语义被状态码短路了。

**修复与证据**：先解析 OAI 错误体，再决定是否回落；用例按**到达形态参数化**（200 / 400 各跑一遍），并留一条反向边界（没有 OAI 错误码的 400 仍按状态码归类）。

**复现**：`tests/tools/test_sources.py::test_pmc_oai_falls_back_to_front_matter_only_after_cannot_disseminate`（200/400 两参数）、`::test_a_non_oai_error_body_is_still_judged_by_status`。

### D-02 子文章的 DOI 顶替了本文的 DOI（#98）

**现象**：PLOS 记录冻结时报 `SOURCE_MISMATCH`，整类记录进不了来源集。

**归因**：`fetch_record` 遍历整棵 `<article>` 取 `article-id[@pub-id-type="doi"]` 且**后写覆盖前写**。PLOS 把开放同行评审文件作为 `<sub-article>` 放在同一条记录里，各自带 `….r001` … `….r006`，排在本文 DOI **之后**，于是 `record.doi` 变成 `….r006`。

**为什么不是相邻那层**：它报的是 `SOURCE_MISMATCH`，读起来像「上游给了另一篇文章」。实际是解析取错了容器——**把解析缺陷说成上游冲突**，会让排查方向整个错掉。

**修复与证据**：只读 `<article>` **直接子元素**的 `front/article-meta`；找不到就返回 `None`，**不回落**到全树——回落等于拿另一篇文章的 DOI 冒充本文身份。真实记录 `PMC13648980` 修复前 freeze 直接失败，修复后冻出 56 段、许可 CC BY；同一份字节上新旧取值分别是 `10.1371/journal.pone.0360355` 与 `….r006`。

**复现**：`tests/tools/test_sources.py::test_a_sub_article_doi_never_stands_in_for_the_article_doi`、`::test_a_plos_shaped_record_is_no_longer_rejected_as_a_doi_mismatch`、`::test_a_record_without_its_own_doi_does_not_borrow_a_sub_article_doi`。

### D-03 `version_hash` 覆盖整个 OAI 响应，每次取回都变（#67）

**现象**：同一 DOI 相隔数秒取回两次，`version_hash` / `source_id` / `paragraph_id` 全变，冻结清单每次运行都报「三个来源全部漂移」。

**归因**：术语表说 `version_hash` 是「取得的 **JATS 原始字节** SHA-256」，实现却对整个 OAI 响应取哈希，而响应含每次请求都不同的 `<responseDate>`。

**为什么不是相邻那层**：现象像「上游内容在变」，实测 `<article>` 子树的哈希与逐段哈希都稳定，只有整包哈希变。

**修复与证据**：哈希改到 `<article>` 子树；`paragraph_id` 因此可以跨次引用，冻结清单才能用 `article_sha256` + 逐段 `ordinal` 定位。

**复现**：`tests/tools/test_sources.py::test_stable_identifiers_survive_a_second_fetch_of_the_same_record`、`tests/tools/test_live_source_contract.py`（live，CI 永久 skip）。

---

## 契约层

### D-04 输出契约只说「包含哪些字段」，没说字段是什么形状（#62）

**现象**：真实模型三轮里 `MODEL_INVALID_OUTPUT` 占 3–5 / 7，`contradicted_object` 上模型连续两次给出**与人工核对一致的标签**和逐字引文，仍整单失败。

**归因**：`_DECISION_SYSTEM` 没说明 `supported_parts` / `scope_differences` / `limitations` 是字符串数组，模型对单值写字符串；更糟的是 `parse_decision_output` 把所有 `ValidationError` 统一包成「动作字段不合法」——修复提示词指向 `action`，实际错在 `decision` 内部，模型无从修正，白耗唯一一次修复额度。

**为什么不是相邻那层**：一直被读成「模型不听话」。原始输出显示模型完全照做，只是字段形状没被声明。

**修复与证据**：提示词声明三个字段是字符串数组；解析错误按字段定位。`MODEL_INVALID_OUTPUT` 由基线 3 例降到修复后两轮均为 **0**。

**复现**：`tests/session/test_workflow.py::test_decision_prompt_declares_the_array_fields_and_a_minimal_shape`、`::test_repair_note_names_every_decision_field_that_broke_the_contract`。

**限制**：这是「结构层」修复，**只证明症状消失，不证明判断变准**。标签正确率没有因此改变。

### D-05 段落 ID 要模型逐字复制 75 字符的不透明串（#74 / #82）

**现象**：`QUOTE_MISMATCH` 每轮稳定 2 / 7；逐字符比对确认引文本体完全正确，失败在 ID：模型写成 `PMC0000001:fff…:1`，**丢了开头 `p:`**。

**归因**：提示词展示的是完整 ID，但没有一句「原样照抄方括号内的 ID，连 `p:` 一起」；而诊断信息只报「段落未进入本次判断的上下文」，没有给出候选里真正的 ID。**要求模型逐字复制一个 75 字符的不透明串，却把这条规则留在提示词外面。**

**为什么不是相邻那层**：`QUOTE_MISMATCH` 的名字指向「引文对不上」，而引文是对的。错误码把 ID 定位问题说成了引文问题。

**修复与证据**：提示词写明照抄规则（`PROMPT_VERSION` 0.2.1）；`_candidate_id_note` 把「漏 `p:`」「带方括号」这类**可恢复**情形翻成候选里的真 ID 写进修复输入——只改诊断，不放宽判据。修后两轮 ID 形状 **7 / 7** 全对、`QUOTE_MISMATCH` 归零、修复调用 0 次。

**复现**：`tests/session/test_workflow.py::test_an_id_that_lost_the_p_prefix_is_repaired_with_the_candidate_id`、`::test_quote_mismatch_after_repair_fails`。

### D-06 顶层多余字段：一个分支报错、另一个分支静默忽略（#79）

**现象**：`retrieve` 分支对顶层多余字段报 `extra_forbidden`，`final` 分支静默忽略。同一个模型、同一类越界，两种结果。

**归因**：两个解析入口一个把整份载荷送进带 `extra="forbid"` 的模型，另一个只挑字段读。严格度成了**解析写法的属性**，而不是契约的属性。

**为什么不是相邻那层**：不是「模型有时守规矩有时不守」，是系统对同一种越界的判据不一致。

**修复与证据**：`final` 分支也送整份载荷；嵌套口径的承重用例在 `tests/adversarial/test_export_boundary.py::test_the_model_cannot_inject_a_bibliographic_field`。

**复现**：`tests/session/test_workflow.py::test_a_stray_top_level_field_in_a_final_response_costs_one_repair_not_the_task`、`::test_a_stray_top_level_field_that_survives_the_repair_is_model_invalid_output`。

---

## 判据层

### D-07 四个标签名进了提示词，判据一个字没进（#78）

**现象**：真实模型两轮合计 14 次最终判定里，标签「部分支持」出现 **0 次**；期望「部分支持」且产出标签的 3 次**全部**被判成「相矛盾」，期望「相矛盾」的 3 次全部判对——**一个类别被整个并入了相邻类别**。

**归因**：`_DECISION_SYSTEM` 只列了四个标签名，判据在 `docs/glossary.md` 与 `docs/prd.md` 里，**没有一个字进入提示词**。可 grep 证实。

**为什么不是相邻那层**：看起来像「模型分不清边界」，实际是系统从未告诉它边界在哪里。这不是模型能力问题，是提示词缺内容。

**修复与证据**：判据写进提示词（0.2.3）：补「方向一致」前提、「只在数量或范围上有出入 → 部分支持」、以及「原文明确否定对象或因果 → 相矛盾」的对称出口；示例**不得取自 `samples/`**（否则复测答对有两种解释），并加了一条「与样本连续 5 字重合即失败」的守卫。

**复现**：`tests/boundary/test_domain_contract.py::test_the_prompt_examples_are_not_taken_from_the_functional_samples`。

**限制（重要）**：**0.2.3 没有在真实模型上复测过**。第三轮的 5 / 7 跑在 0.2.1 上，剩下 2 例（`partial_population_scope`、`partial_quantity`）就是本条的靶子。所以本条只能记「结构性缺口已补」，不能记「边界已判对」。要下后者需要一次带密钥的真实运行。

---

## 账务层

### D-08 冻结快照记的是配置里的模型名，不是实际调用的模型（#68）

**现象**：换上游后 `config_snapshot()` 与 `config_digest` 不变，诊断包里看不出这次到底调了谁。

**归因**：快照里只有 `configured_model`（常量，如 `agnes-2.5-flash`），而真实调用的是 `provider_model`（如 `deepseek/deepseek-flash`）。**字段有值不等于值对**。

**为什么不是相邻那层**：不是导出时漏脱敏或漏字段，是快照采集点选错了变量。

**修复与证据**：`provider_model` 进快照并进 `config_digest`；验收记录里两列并排显示，可对账。

**复现**：`tests/boundary/test_domain_contract.py::test_the_dispatched_provider_model_is_part_of_the_frozen_digest`。

### D-09 修复请求的 `round` 硬编码为 1，反向指针指向不存在的请求（#70）

**现象**：`repairs_request_id` 写成 `<case>:decision:1`，但该 case 只有 1 次 `decision`（没有补读轮），指针 100% 指向不存在的东西。实例从 2 处增加到 7 处。

**归因**：修复请求的轮次硬编码，没跟随「它所修的那个请求」的轮次；判别式也取错了量（取轮次，而不是该任务内第几次修复）。

**为什么不是相邻那层**：看起来像「补读轮的命名不一致」，实际是没有补读轮时也照样写 1。

**修复与证据**：`request_id` = `{task}:output_repair:{第几次}`，`round` 记被修请求的轮次；`model_calls` 写入从 `INSERT OR REPLACE` 改为普通 `INSERT`（重复即本地故障，不再静默覆盖）。修后两轮 14 次调用 `repairs` 全为空，没有新实例。

**复现**：`tests/session/test_workflow.py::test_a_quote_repair_points_at_the_first_round_decision`、`::test_a_quote_repair_after_a_supplemental_round_points_at_decision_one`。

### D-10 「没有 Retry-After」与「Retry-After: 0」被当成同一件事（#69）

**现象**：429 / 5xx 不带 `Retry-After` 时立即重试；带 `0` 时也按同一路径处理。一处等、一处不等。

**归因**：`_retry_after*` 把「没有该响应头」（`None`，应取下限）与「明确说 0」（`0.0`，应立即重试）都读成 0。

**为什么不是相邻那层**：不是「退避参数没配」，是两个语义被合并成一个值。恢复策略的常量已单源到 `domain/rules.py`，由 `sources/http.py` 与 `models/sdk.py` 共用。

**复现**：`tests/tools/test_sdk_gateway.py::test_an_upstream_retry_after_is_waited_out`、`tests/performance/test_worker_deadline.py::test_a_retry_after_within_the_remaining_time_is_waited_out_then_retried`、`::test_a_retry_after_beyond_the_remaining_time_is_not_waited_out`。

---

## 方法层（不是产品缺陷，但让上面几条晚了很久才被发现）

### D-11 测试替身把上游的错误形态写死（#28 / #57 / #61 同族，四次复现）

**现象**：mock 只造 200 形态的成功响应，于是「上游用哪个状态码送错误体」这件事被固定在测试里。回落分支在真实上游上**一次都没执行过**，而测试全绿。

**归因**：「回放式验收对真实输出形状没有鉴别力」。用替身跑通，只能证明管道连上了，不能证明管道在上游真实行为下成立。

**处置**：上游错误路径按**到达形态参数化**（200 / 400 各跑一遍）+ 反向边界；真实模型验收**必须固定记录原始输出**（`semantic-acceptance-live.md`）。本轮正是靠原始输出才把 `MODEL_INVALID_OUTPUT` 定位到 `scope_differences`、把 `QUOTE_MISMATCH` 定位到丢掉的 `p:`。

**复现**：`tests/tools/test_sources.py::test_pmc_oai_falls_back_to_front_matter_only_after_cannot_disseminate` 的参数化本身就是这条的产物。

### D-12 报告可复现性依赖平台（2026-10-15）

**现象**：`report.py --check` 在 CI 与本地给出不同结果。

**归因**：产物里含平台相关字段，接入 CI 才暴露。

**处置**：报告只保留由样本集决定的字段，显式不带 `git rev-parse HEAD` 这类每次提交都变的字段；`--check` 改为逐字节比对。

**复现**：`tests/functional/test_report_metrics.py`、`PYTHONPATH=backend python tests/functional/report.py --check`。

---

## 不是缺陷的三条（避免后续读者重复立项）

| 事项 | 为什么不是缺陷 |
| --- | --- |
| #28 非 OA 只给题录+摘要时阻断判定 | 这是**产品口径**，不是 bug。落在 `graph/workflow.py::_prepare_source` 且**在冻结之后**，终态复用 `CONTENT_INCOMPLETE`。真实非 OA 记录目前都先停在 `LICENSE_UNKNOWN`，所以这条门禁今天是防御性的（45 条真实非 OA 抽样中 0 条带 CC BY）。 |
| #71 `vite preview` 没有 `/api` 代理 | 经实测是**更正而非修复**：Vite 的 `preview.proxy` 默认继承 `server.proxy`。已按「非缺陷」关闭。 |
| #86 `claims` 覆盖率 | 是**未完成**，不是缺陷。`--require-coverage` 只认已签核的条目；未签核不算覆盖。 |

## 还没归因 / 还没验证的

| 项 | 状态 | 为什么不糊过去 |
| --- | --- | --- |
| #78 的 0.2.3 提示词 | 结构性缺口已补，**真实模型未复测** | 本机无模型密钥；不能用 stubbed upstream 顶替，那正是 D-11 说的那种假证据。 |
| 观测留档（执行记录、模型调用、`langfuse_enabled`） | **缺密钥，未截图** | 没有密钥时任务停在 `query_generation / UPSTREAM_UNAVAILABLE`，`model_calls` 是空的；拿这样的包当留档会误导。 |
| 真实来源集的四项指标 | 分母还不完整 | `PMC13648980` 仍是 0 条 claims；其余三篇 16 条已签核 15 条、1 条因措辞歧义打回。 |
| 模型调用的 token / 成本 | 未纳入归因 | `ModelAttempt.usage` 在调用账里、不在 `ExecutionRecord` 里，要做成 Langfuse 的 generation 需另开 sink（`decisions.md`「观测导出接入」已记为未做项）。 |

## 怎么用这份报告

单条缺陷的现场归因，不要靠复述本文件，跑：

```bash
PYTHONPATH=backend python tests/functional/triage.py packet.json
PYTHONPATH=backend python tests/functional/triage.py packet.json --expect-ordinal 39 --expect-label 支持
```

它按 [triage.py](../tests/functional/triage.py) 的 code 输出**主因 + 证据字段 + 被排除的原因**。没有 `--expect-ordinal` 时它**不会**判「检索遗漏」——「候选为空」只能说明没检索到东西，不能说明正确的那段被漏了。这一条限制是刻意的：凭猜测写出来的归因不可复现。
