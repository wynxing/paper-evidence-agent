# 七维度用例清单

这份文档回答一个问题：**`docs/test-plan.md` 里的七个维度，各自靠哪些用例判、按什么前提判、判据是什么。**

- **判据的权威在 `docs/test-plan.md:40-121`**。本文档不新增判据、不放宽判据，只把已有判据落到具体用例上，并标出**没有用例接住的判据**（附录 B）。
- **不是"用例目录"**。用例的真实位置在 `tests/`，本文档不复制代码，只写「哪条用例钉住哪句判据」。
- **数字口径**：2026-10-22，`main = 3e560cb` + 本文件附录 B 所记的 10 条新增用例，`pytest tests` 收集 **443** 条，**414 passed / 29 skipped**。跳过项全部是网络门控的 live 检查（附录 A.2），不是被删的用例。

## 0. 总览

### 0.1 七个维度与实跑数字

| 维度 | 主目录 | 收集 | 通过 | 跳过 | 判据条数 | 独立复跑 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 功能准确性 | `tests/functional/` | 83 | 70 | 13 | 11 | `pytest tests/functional` |
| 2 工具调用 | `tests/tools/` | 167 | 151 | 16 | 10 | `pytest tests/tools` |
| 3 RAG | `tests/retrieval/` | 12 | 12 | 0 | 7 | `pytest tests/retrieval` |
| 4 任务内澄清、隔离与多步执行 | `tests/session/` | 38 | 38 | 0 | 8 | `pytest tests/session` |
| 5 对抗与安全 | `tests/adversarial/` | 31 | 31 | 0 | 5 | `pytest tests/adversarial` |
| 6 边界与异常 | `tests/boundary/` | 71 | 71 | 0 | 13 | `pytest tests/boundary` |
| 7 性能 | `tests/performance/` | 21 | 21 | 0 | 5 | `pytest tests/performance` |
| **七维合计** | — | **423** | **394** | **29** | **59** | `pytest tests` |

另有两块**不属于七维度**、但同样在 `#93` 里交付的内容：

| 内容 | 目录 | 收集 | 归属说明 |
| --- | --- | --- | --- |
| 界面主路径 | `tests/e2e/` | 16（Playwright） | `test-plan.md:128` 明说它「不替代上面各维的判定」，故不并入七维 |
| 缺陷归因链路 | `tests/functional/test_triage.py` | 20 | 对应 `test-plan.md` §1「外部测试 Agent」，不是七维之一 |

423 + 20 = 443，与 `pytest tests` 的收集数一致。

### 0.2 维度与目录不是一一对应（先看这条，否则会数错）

`test-plan.md` 给每个维度标了「目录」，那是**主目录**。实际有不少判据由主目录之外的用例接住，最典型的三处：

| 判据 | 主目录里没有 | 实际所在 |
| --- | --- | --- |
| 首次检索为空必须补读、补读仍空才落证据不足 | `tests/retrieval/` 只到查询编译与索引 | `tests/session/test_workflow.py`（要跑完整 graph 才有"首次为空"） |
| 各错误码的终态映射 | `tests/boundary/` 只测映射表本身 | `tests/tools/test_sources.py`（连接器侧真实分支）、`tests/session/test_workflow.py`（工作流落点） |
| `accounting=unverified`、usage 缺失不写零 | 属边界维度 | `tests/performance/test_worker_measurements.py` |

所以**按目录统计通过率会漏**。本文档按判据归位，附录 A 给文件级对照。

### 0.3 怎么复跑

```bash
# 全量：在仓库根目录执行（Windows 用 Scripts/python.exe，Linux/macOS 用 bin/python）
# -c 与 --basetemp 不能省：缺前者触发 fail-closed shim，缺后者会复用上一次的临时目录
backend/.venv/Scripts/python.exe -m pytest tests -c backend/pyproject.toml --basetemp="$TEMP/pe-run" -q

# 只跑某一维
pytest tests/functional -c backend/pyproject.toml --basetemp="$TEMP/pe-fa" -q

# live 类（默认跳过，需要真实外网）
PAPER_EVIDENCE_LIVE_SOURCES=1 pytest tests/functional/test_live_frozen_sources.py -c backend/pyproject.toml -q
```

`tests/e2e/` 是独立的 Node 项目，另需 `npm --prefix tests/e2e ci` 与四个空闲端口（8000/5173/8765/8001），跑法见 `tests/e2e/README.md`。

---

## 1. 功能准确性

### 1.1 这一维判什么、不判什么

**判**：给定一句论断与一篇冻结的真实文献，智能体给出的四类标签与逐字引文，是否与人工核对结论一致；以及用于产成绩的验收器自己是否可信（负向控制）。

**不判**：不以 SciFact 摘要成绩、模拟输出或一次演示替代真实全文语义测试（`test-plan.md:73`）。本维的语义结论**只来自 4 篇 CC BY 真实来源上的 24 条人工答案**。

### 1.2 前提

- 冻结清单在 `tests/functional/sources/*.json`，只存段落哈希与 120 字预览，**不存正文**；正文按需从 PMC 取回。
- `claims` 必须有人工签核（`review.outcome = agree`）才算真值；未签核的只算候选。
- 语义成绩只在**验收器负向控制通过**之后才能发布（`test-plan.md:47`）。

### 1.3 步骤

1. `freeze_sources.py --check` 确认四篇正文未漂移；
2. `claims.py --live` 逐条把引文在冻结段落里定位（离线只能判落在 120 字预览内的 6 条）；
3. 跑语义验收，得到标签与关键约束的一致数；
4. 跑负向控制（故意给错标签、错引文），确认验收器会拒；
5. 按 `evaluation.md §4` 出分母（N/A 不补 0，拒判不从分母移除）。

### 1.4 判据与对应用例

| 编号 | 判据 | 前提 | 步骤 | 对应用例 |
| --- | --- | --- | --- | --- |
| FA-1 | 冻结样本的实际判定必须等于人工核对标签 | 该条 `claims` 已 `agree` | 跑一次判定，比对 `expected_label` | `test_a_frozen_case_matches_its_human_checked_label` |
| FA-2 | 判定针对冻结版本，不随后续取回漂移 | 清单哈希与取回一致 | 取回两次算哈希，或用旧版本断言拒绝 | `test_a_frozen_case_is_judged_against_the_frozen_version`、`test_a_frozen_source_still_matches_today_upstream`（live） |
| FA-3 | 验收器**必须拒**错标签、错引文、无证据的确定判断；同时**必须通过**正确结果（防永远拒判） | 已有正确结果作正对照 | 分别投喂错标签/错引文/无证据，再跑正对照 | `test_the_evaluator_rejects_a_wrong_label_and_a_mismatched_quote`、`test_the_evaluator_rejects_a_definitive_label_without_evidence`、`test_a_sample_that_points_at_a_missing_paragraph_is_refused`、`test_a_quote_outside_the_frozen_paragraph_cannot_become_a_definitive_label` |
| FA-4 | 应可判定的样本不能全部落成证据不足 | 验收集非空 | 统计四类标签分布，断言存在非拒判判定 | `test_the_frozen_set_is_decidable_rather_than_all_refusals` |
| FA-5 | 引文必须逐字可定位：改写的句子不算、只差空白的算、段号不存在或引文长于整段要拒 | 有冻结段落 | 用改写/空白差异/超长引文分别投喂 | `test_a_paraphrased_quote_is_not_locatable`、`test_a_quote_that_differs_only_in_whitespace_is_locatable`、`test_a_quote_for_a_missing_ordinal_is_rejected`、`test_a_quote_longer_than_its_paragraph_is_rejected` |
| FA-6 | 离线预览不完整时**既不判死也不静默放过**；live 取回丢段要显式报告 | 引文落在 120 字预览之外 | 离线跑一次看是否报"无法判定"，再 live 跑一次 | `test_offline_a_truncated_preview_never_condemns_a_quote`、`test_offline_a_truncated_preview_never_passes_a_quote_silently`、`test_a_quote_found_inside_the_preview_counts_as_checked`、`test_a_live_fetch_that_lost_a_paragraph_is_reported` |
| FA-7 | 覆盖门禁只认**已签核**的 claim；`disputed` 留在清单但不进分母 | 混有未签核与 disputed | 跑 `--require-coverage` 与 `--require-review`，看退出码 | `test_an_unsigned_claim_cannot_satisfy_the_coverage_gate`、`test_only_signed_claims_are_counted_by_the_gate`、`test_a_disagreed_claim_is_signed_but_not_confirmed`、`test_a_disputed_claim_stays_in_the_file_but_out_of_the_denominator` |
| FA-8 | `claims` 形状必须可校验：缺 `claim_kind`、枚举外取值、非证据不足却无引文、重复 id 都要拒 | 夹具构造条目 | 逐条投喂畸形记录 | `test_a_claim_without_a_kind_is_rejected`、`test_a_kind_outside_the_known_vocabulary_is_rejected`、`test_evidence_is_required_unless_the_label_is_insufficient`、`test_duplicate_claim_ids_are_rejected`、`test_a_half_written_claim_cannot_pass` |
| FA-9 | 指标分母口径：零分母写 N/A 不写 0/100；拒判与执行失败留在召回分母；误判与过度拒判分列 | 有报告生成器 | 构造边界计数后看渲染 | `test_a_zero_denominator_is_rendered_as_not_applicable`、`test_refusal_and_failure_stay_in_the_recall_denominator`、`test_locatability_is_not_applicable_when_nothing_was_published`、`test_misjudgement_and_over_refusal_are_reported_separately`、`test_macro_f1_excludes_classes_whose_denominator_is_zero`、`test_pending_slots_mark_the_whole_report_provisional` |
| FA-10 | 冻结集形状：至少 3 个来源、许可在白名单内、清单内不得内嵌正文 | 清单已提交 | 读清单断言结构与许可 | `test_the_frozen_set_has_the_expected_shape`、`test_every_frozen_source_is_under_a_supported_licence` |
| FA-11 | 原文位置可展示：证据上下文接口返回被引段与两侧邻段，边界段只向内扩展，跨来源不串 | 真实冻结来源（live） | 取回邻段并与冻结文本逐字比对 | `test_evidence_context_expands_both_ordinal_neighbours`、`test_a_boundary_anchor_expands_only_inward`、`test_evidence_context_never_reads_across_sources`（tools 同名断言）、`test_an_unknown_paragraph_id_expands_to_nothing` |

### 1.5 这一维的现状与缺口

- **24 条人工答案**（`PMC1182327` 6 / `PMC7461750` 3 / `PMC8806060` 7 / `PMC13648980` 8），四类标签 9/4/6/5，五个变体全覆盖；**24 条已全部签核**（`#109` 重签 `c07` 后关闭 `#86`），`--require-coverage` / `--require-review` / `--live` 三道门禁均 exit 0。
- **缺口**：`test-plan.md:47` 要求「邻段可能同样支持论断，不能仅因更换邻段就硬设失败」。现有负向控制覆盖了「正确结果必须通过」，但**「把引文换成邻段」这一变体没有专门断言**。
- **缺口**：`Recall@k` 明确不在本验收集产出（`report.py` 与 `semantic-report.md` 均声明），不是遗漏，但评分时必须写"不适用"而不是 0。

---

## 2. 工具调用

### 2.1 这一维判什么、不判什么

**判**：应用对上游（模型、来源连接器）的调用是否**经当前配置**、是否**按预算重试**、失败是否**映射成独立错误码**、每次尝试是否**留有记录**。

**不判**：不判模型答得好不好（那是功能准确性）。模拟上游通过**不代表**真实上游已联通，真实接入另列结果。

### 2.2 前提

- 上游全部换成本机替身（可控网关 / 假 SDK），除标注 `real` 的少量用例。
- 配置里只改别名映射即可切换测试上游，**不改业务代码**。

### 2.3 步骤

1. 建任务时先过确认门（来源、接收方、预算），拿 `config_digest`；
2. 用替身网关按状态码/异常类型逐类触发；
3. 读 `model_calls` 表断言：尝试次数、`request_id`、usage、最终错误码；
4. 对连接器态另跑 OAI 端点断言（是否离开官方只读路径）。

### 2.4 判据与对应用例

| 编号 | 判据 | 前提 | 步骤 | 对应用例 |
| --- | --- | --- | --- | --- |
| TO-1 | 未确认来源、未授权接收方、摘要过期时**不入队、不调模型**（过期返回 409） | 有合法 DOI | 缺一个确认项或改配置后提交 | `test_create_requires_confirmations_and_a_valid_doi`、`test_create_rejects_a_stale_config_digest_without_a_task`、`test_create_rejects_recipients_outside_the_configured_scope`、`test_authorized_recipients_may_narrow_but_never_widen` |
| TO-2 | 请求确实经过当前配置的模型传输；SDK 形态不偷偷换端点、断开 Proxy 不直连供应商 | 配置指定别名与端点 | 抓替身网关收到的 wire payload 与端点 | `test_the_wire_payload_uses_the_configured_mapping_not_the_alias`、`test_the_attempt_records_the_model_the_sdk_actually_dispatches`、`test_unset_endpoint_and_key_are_not_sent_at_all`、`test_the_configured_transport_decides_which_gateway_is_built` |
| TO-3 | 错误码各自独立：429 耗尽→`UPSTREAM_RATE_LIMITED`、超时→`UPSTREAM_TIMEOUT`、连接/暂时性→`UPSTREAM_UNAVAILABLE`、认证→`UPSTREAM_AUTH_FAILED`、参数→`UPSTREAM_INVALID_REQUEST` **不重试** | 替身按类抛错 | 每类各跑一次，断言码与是否重试 | `test_http_status_maps_to_independent_upstream_codes`、`test_connection_error_is_upstream_unavailable`、`test_timeout_is_upstream_timeout`、`test_malformed_success_body_is_invalid_request`、`test_every_litellm_failure_class_maps_to_an_upstream_code`、`test_a_failure_that_is_not_recoverable_is_not_retried`、`test_the_last_failure_decides_the_reported_code` |
| TO-4 | 恢复最多「首次 + 一次」，且不越过任务剩余预算；客户端自身不再重试 | 任务剩余时间足够 | 连续失败两次，看尝试条数与最终码 | `test_client_does_not_retry_a_transient_failure`、`test_a_recoverable_failure_is_retried_once_and_both_attempts_are_recorded`、`test_recovery_stops_at_the_configured_budget`、`test_the_attempt_cap_is_never_more_than_the_task_has_left`、`test_client_side_recovery_stays_off` |
| TO-5 | `Retry-After` 大于剩余时间时不再发起重试；小于时等待后重试 | 上游回 429/503 + Retry-After | 两种取值各跑一次 | `test_an_upstream_retry_after_is_waited_out`、`test_a_retry_after_longer_than_the_task_does_not_burn_the_remaining_budget`、`test_recovery_needs_the_task_to_still_have_time` |
| TO-6 | 来源连接器只访问官方只读端点，重定向与错误体都不得把请求带离官方路径 | 真实/替身 OAI 端点 | 构造重定向、非 OAI 错误体、405 场景 | `test_default_pmc_oai_endpoint_is_the_canonical_api_path`、`test_pmc_oai_falls_back_to_front_matter_only_after_cannot_disseminate`、`test_pmc_oai_errors_other_than_cannot_disseminate_are_not_retried`、`test_a_non_oai_error_body_is_still_judged_by_status`、`test_pmc_oai_call_follows_redirects`、`test_a_redirect_without_following_is_rejected_not_parsed` |
| TO-7 | 来源身份与许可闸门：DOI 解析各分支落**不同**错误码，不得合成"来源不存在" | 构造各分支响应 | 逐分支断言 HTTP 状态与错误码 | `test_crossref_404_with_agency_confirmed_is_metadata_not_found`、`test_crossref_404_with_other_agency_is_unsupported`、`test_agency_missing_and_resolver_miss_is_doi_unresolvable`、`test_doi_mismatch_between_crossref_and_pmc_is_blocked`、`test_a_sub_article_doi_never_stands_in_for_the_article_doi`、`test_non_english_body_is_language_unsupported`、`test_unsupported_or_unknown_licenses_are_blocked` |
| TO-8 | 每次尝试（失败与成功）都关联 `request_id`；usage/模型版本缺失记 `null` 不写零 | 替身不返回 usage | 跑一次成功 + 一次失败，读调用账 | `test_success_records_one_attempt_and_keeps_unknown_fields_null`、`test_failed_and_successful_calls_share_the_params_digest`、`test_missing_usage_and_missing_ids_stay_null_rather_than_zero`、`test_success_records_the_call_id_the_sdk_would_have_sent_as_a_header`、`test_a_real_sdk_call_returns_a_call_id_and_usage` |
| TO-9 | 总时限先到时记为任务超时，**不计作一次上游尝试** | 时钟已耗尽 | 在 deadline 后发起调用 | `test_expired_deadline_is_task_timeout_not_an_attempt` |
| TO-10 | HTTP 错误信封与校验错误：机器可读错误码、不回显输入值、定位到字段与数组下标、创建冲突不带任务 | 有测试路由与真实路由 | 分别触发契约错误、框架错误、校验错误与创建冲突 | `test_preview_contract_errors_keep_machine_readable_codes`、`test_unmapped_contract_errors_are_not_reclassified`、`test_framework_http_errors_preserve_headers_and_log_only_safe_structure`、`test_validation_errors_expose_locations_without_input_values`、`test_validation_errors_locate_query_fields_and_array_indices`、`test_creation_conflict_needs_no_task_and_task_conflict_requires_state` |

### 2.5 这一维的现状与缺口

- `tests/tools/test_live_source_contract.py` 的 **16 条全部 skip**（`PAPER_EVIDENCE_LIVE_SOURCES=1` 才跑）。它验的是 PMC 真实契约，**CI 永久 skip ≠ 已验证**，评测时要说明这 16 条是否在本机跑过。
- `test_a_real_sdk_call_returns_a_call_id_and_usage` 与 `test_a_real_sdk_failure_reaches_the_same_mapping` 依赖本机可用的真实 SDK 路径，非纯替身。

---

## 3. RAG

### 3.1 这一维判什么、不判什么

**判**：检索是否**只在本任务冻结来源内**、查询编译是否**不会把普通词变成 MATCH 操作符**、切分是否**确定性可复现**、首次为空是否**必须补读**、补读仍空是否落 `RETRIEVAL_EMPTY`。

**不判**：首版不引入向量库，`Recall@k` 不作为通过条件（`tech-stack.md:142`）。

### 3.2 前提

- 冻结来源已建立 FTS5 索引；每个来源有独立的 `source_id` 命名空间。
- 检索输入既可能是中文论断，也可能带引号/括号/操作符原文。

### 3.3 步骤

1. 用裸引号、未闭合括号、`AND/OR/NOT`、`NEAR(`、冒号、星号、纯标点分别构造查询；
2. 断言编译结果的 MATCH 表达式与预期一致，且不出现裸操作符；
3. 同一 JATS 解析两次，比对段落 ID/文本/哈希；
4. 换版本哈希后断言旧 ID 不指向新段落；
5. 走完整 graph 验「首次为空 → 补读」两支。

### 3.4 判据与对应用例

| 编号 | 判据 | 前提 | 步骤 | 对应用例 |
| --- | --- | --- | --- | --- |
| RG-1 | 合法普通词编译后不得成为 MATCH 操作符；括号/引号/标点不得让查询编译出语法错 | 有可用索引 | 逐类输入看编译产物 | `test_compile_match_quotes_terms_and_joins_with_or`、`test_compile_match_never_emits_bare_operators`、`test_compile_match_rejects_punctuation_only_queries`、`test_compile_match_doubles_inner_quotes_and_dedupes` |
| RG-2 | 同一 JATS + 同一解析器两次解析必须产生相同 ID/文本/哈希（确定性冻结） | 有 JATS 字节 | 解析两次逐字段比对 | `test_parse_jats_is_deterministic_and_freezes_text`、`test_parse_jats_keeps_the_ordinal_it_counted_in_the_paragraph_id`、`test_parse_jats_names_an_unwrapped_paragraph_after_its_container` |
| RG-3 | 换版本后旧 `paragraph_id` 不得指向新段落（命名空间隔离） | 有旧版本哈希 | 换 `version_hash` 再查旧 ID | `test_new_version_hash_produces_a_new_namespace` |
| RG-4 | 检索只在当前来源内；索引故障→`RETRIEVAL_FAILED`，不得变成 `RETRIEVAL_EMPTY`，也不消耗输出修复次数 | 有索引 | 注入索引故障与跨来源段落 ID | `test_retrieval_is_source_scoped_and_fault_aware`、`test_retrieval_index_fault_is_retrieval_failed`、`test_retrieval_reports_unindexable_queries_as_output_problem` |
| RG-5 | 首次检索为空不得直接结束；补读仍空才落证据不足/`RETRIEVAL_EMPTY` | 替身首轮返回空 | 跑完整 graph 看是否发起补读 | `test_first_empty_retrieval_requests_a_supplemental_round`、`test_two_empty_rounds_yield_insufficient_evidence`、`test_first_empty_retrieval_rejects_a_neighbour_only_retrieve` |
| RG-6 | 邻段可用：只给邻段 ID 的 retrieve 也能取到段落 | 首轮非空 | 发 `neighbor_paragraph_ids` 单轮 | `test_neighbour_only_retrieve_reads_neighbours` |
| RG-7 | 中文论断→英文正文受支持；英文论断→中文正文须 `SOURCE_LANGUAGE_UNSUPPORTED` | 有中/英来源 | 两侧各发一次 | `test_non_english_body_is_language_unsupported`（来源侧闸门；检索侧无专门用例，见缺口） |

### 3.5 这一维的现状与缺口

- **缺口（明确）**：`tests/retrieval/` 里**没有** unicode61 中文子词召回盲区的用例，也没有「中文论断→英文正文」的成功路径用例。`test-plan.md:100` 明确要求这两条。当前只有来源侧的语言闸门（`SOURCE_LANGUAGE_UNSUPPORTED`）挡住了「英文论断→中文正文」，**不等于检索侧跨语言能力已验证**。
- **缺口（精确说）**：`test_first_empty_retrieval_requests_a_supplemental_round` 在 **graph 层**覆盖了「首轮为空 → 补读 → 落判断」（断言 `supplemental_rounds_used == 1`、轮次 `[0,0,1]`、最终标签 `支持`）。但**检索层没有一条用例验证「改写后的查询真的命中」**——`ScriptedGateway` 把检索结果脚本化，`tests/retrieval/` 的 12 条只覆盖查询编译、解析确定性与故障码，不覆盖「换一种查询才能召回」。同义改写的召回同理。
- `Recall@k` 按设计不产出（`report.py:351`）。

---

## 4. 任务内澄清、隔离与多步执行

### 4.1 这一维判什么、不判什么

**判**：单任务的**步数预算**（主 3 + 修复 1，整任务 ≤ 8 次上游尝试）、修复的**三个分支互斥**、取消与超时的**优先级**、任务之间的**隔离**。

**不判**：**不声称支持通用多轮聊天**。这里的"澄清"是任务内澄清（改写/拆分后重新提交），不是对话记忆。

### 4.2 前提

- 用 `ScriptedGateway` 回放固定决策序列，可精确控制"第几次请求返回什么"。
- 预算常量来自 `config`（45s / 180s / 主 3 / 修复 1），**不能靠环境变量加宽**。

### 4.3 步骤

1. 按决策序列驱动 workflow，记录每次请求的动作与次数；
2. 对四条修复路径各跑一次（查询生成修复、判断修复、伪造摘录修复、修复仍失败）；
3. 在关键节点注入取消与超时，看终态归谁；
4. 检查 `previous_id` 链与模型上下文是否隔离。

### 4.4 判据与对应用例

| 编号 | 判据 | 前提 | 步骤 | 对应用例 |
| --- | --- | --- | --- | --- |
| SS-1 | 默认路径：查询生成 → 检索 → 判断，产出可定位证据的确定标签 | 一次性好的决策序列 | 跑一遍完整 workflow | `test_happy_path_publishes_a_supported_label_with_locatable_evidence` |
| SS-2 | 补读路径最多增加**一轮**检索与一次最终判断，不因"补读"放大主请求数 | 首轮为空 | 数 `main_requests` 与总请求数 | `test_first_empty_retrieval_requests_a_supplemental_round`、`test_a_quote_repair_after_a_supplemental_round_points_at_decision_one` |
| SS-3 | 预算耗尽必须在**派发前**失败（`BUDGET_EXCEEDED`），不是发出去再拒 | 走到第 4 个主请求 | 观察派发次数与终态 | `test_budget_exhaustion_fails_before_dispatch`、`test_two_repairs_of_one_decision_keep_two_distinct_request_ids` |
| SS-4 | 三条修复支互斥：①请求 3 输出 retrieve 时用已有材料修成 final；②修复仍错→`MODEL_INVALID_OUTPUT`；③伪造摘录修复一次后仍不匹配→`QUOTE_MISMATCH` | 分别构造三种坏决策 | 每种各跑一次，断言终态与错误码 | `test_final_on_empty_retrieval_is_repaired_into_a_supplemental_query`、`test_unlocatable_quote_is_repaired_once_then_published`、`test_quote_mismatch_after_repair_fails`、`test_unparsable_repair_output_fails_as_model_invalid_output`、`test_definitive_label_without_evidence_is_repaired_then_published` |
| SS-5 | 证据不足允许无引文发布；确定标签无证据必须先修 | 决策给确定标签且 `evidence` 为空 | 跑一次看是否触发修复 | `test_insufficient_evidence_may_publish_without_evidence`、`test_definitive_label_still_without_evidence_fails_as_quote_mismatch` |
| SS-6 | 契约外字段只扣一次修复额度，不得直接判失败，也不得静默接受 | 响应多一个顶层字段 | 跑一次看请求数与终态 | `test_a_field_outside_the_contract_is_rejected_at_the_top_level_in_both_branches`、`test_a_stray_top_level_field_in_a_final_response_costs_one_repair_not_the_task`、`test_a_stray_top_level_field_that_survives_the_repair_is_model_invalid_output` |
| SS-7 | 取消与超时优先于工作流结果：受理的取消、先到的总时限都覆盖后续成功 | 在最终模型调用/失败前注入取消 | 两个时序各跑一次 | `test_accepted_cancel_wins_over_workflow_result`、`test_cancel_accepted_during_the_final_model_call_wins`、`test_cancel_accepted_before_a_failure_still_wins`、`test_total_deadline_fails_as_task_timeout` |
| SS-8 | 任务间隔离：重试新建任务、`previous_id` 关联可查，但**模型上下文不继承原任务** | 已有终态任务 | 用 `previous_id` 建新任务，检查请求里是否带旧论断 | `test_previous_id_must_exist`、`test_the_input_route_keeps_the_link_to_the_original_task`（**只到链路层，见缺口**） |

### 4.5 这一维的现状与缺口

- **缺口（明确）**：`test-plan.md:114` 要求「覆盖多主张输入返回拆分提示，作者改写或拆分后重新确认提交」。**仓库里没有这条断言**——`tests/session/` 与 `tests/tools/` 都找不到"多主张 → 提示拆分"的用例；e2e 的 `06-revise-and-delete` 只覆盖"修改原句后新建关联任务"，不是拆分提示。
- **缺口**：`test-plan.md:114` 还要求「上一条论断不得进入下一条任务」。现有用例只断言 `previous_id` 存在与形状，**没有断言第二次任务的模型请求里不含上一条论断**。这条只能靠 `#20` 的手工联调确认。

---

## 5. 对抗与安全

### 5.1 这一维判什么、不判什么

**判**：来源文本里的指令能否改变任务目标、能否让模型指定任意网址、能否让连接器离开官方端点；敏感值会不会从导出/日志里漏出去；观测导出是否默认关闭且故障不影响任务。

**不判**：**不把仓库做成通用越狱研究平台**（`test-plan.md:120`）。

### 5.2 前提

- 构造含指令注入的来源文本，以及带敏感标记（如 `SECRET-…`）的夹具。
- 导出分三种视图：本地预览（redacted）、同意后导出（consented）、观测（langfuse，默认关）。

### 5.3 步骤

1. 把注入指令放进来源正文，跑完整流程，看查询阶段与判断阶段的输入；
2. 扫描 stdout、日志、异常、回调载荷与 redacted 导出，找敏感标记；
3. 比对 redacted 与 consented 两个视图的差异是否**只在被门控的文本**上；
4. 打开/关掉观测，跑同一任务比对结果与本地记录。

### 5.4 判据与对应用例

| 编号 | 判据 | 前提 | 步骤 | 对应用例 |
| --- | --- | --- | --- | --- |
| AD-1 | 来源文本中的指令只能作为数据处理，不得改变任务目标、不得进入查询生成、不得让模型编造书目或指认未进入上下文的段落 | 注入型来源文本 | 跑完整流程，检查查询与判断输入 | `test_an_instruction_inside_the_source_reaches_the_model_as_data`、`test_the_injection_does_not_reach_the_query_stage_and_keeps_the_task_goal`、`test_the_model_cannot_cite_a_paragraph_that_never_entered_the_context`、`test_the_model_cannot_supply_the_bibliography` |
| AD-2 | 恶意 DOI 不得把请求带离官方端点 | 构造畸形/重定向 DOI | 观察实际请求目标 | `test_a_hostile_doi_cannot_move_a_request_off_the_official_endpoint` |
| AD-3 | 敏感标记不得出现在 redacted 导出、理由与限制字段、失败任务的导出里；自由文本字段一律占位符 | 带标记的失败/成功任务 | 导出后逐字段扫描 | `test_the_redacted_packet_carries_no_sensitive_marker`、`test_reason_and_limitation_fields_are_redacted_too`、`test_every_free_text_field_in_the_redacted_packet_is_a_placeholder`、`test_a_failed_run_is_redacted_the_same_way`、`test_the_consented_packet_keeps_the_claim_as_a_control` |
| AD-4 | 导出授权与模型同意分开；redacted 保留公开书目且预览要明示"书目未遮盖"；同意视图与 redacted 只差被门控的文本 | 有可导出任务 | 分别取三种视图比对 | `test_the_redacted_packet_keeps_the_public_bibliography`、`test_the_redacted_packet_still_masks_the_claim_while_keeping_the_bibliography`、`test_the_model_cannot_inject_a_bibliographic_field`、`test_the_redacted_and_consented_views_differ_only_by_the_gated_text`、`test_the_consented_view_records_the_recipient_locally` |
| AD-5 | 观测默认关闭、配置不全不启用；启用后故障不改变核验结果、不增加业务重试；span 只带白名单标识不带内容 | 有/无观测配置 | 开关各跑一次，比对结果与 span 字段 | `test_langfuse_is_off_unless_explicitly_enabled`、`test_a_partial_langfuse_configuration_is_not_enabled`、`test_enabling_observability_does_not_change_the_task`、`test_spans_carry_only_allow_listed_identifiers_and_never_the_content`、`test_a_broken_exporter_changes_neither_the_result_nor_the_local_record`、`test_a_sink_that_raises_does_not_fail_a_step` |

### 5.5 这一维的现状与缺口

- `test-plan.md:115` 要求「在正常、失败和重试路径注入敏感标记」。现有用例覆盖**正常与失败**（`test_a_failed_run_is_redacted_the_same_way`），**重试路径**没有单独断言。
- 观测的 5 项 env 齐备才导出，这一行为有 `test_a_partial_langfuse_configuration_is_not_enabled` 钉住；`langfuse_enabled=false` 的实机截图属 `#93`「观测留档」交付项，不在自动化用例里。

---

## 6. 边界与异常

### 6.1 这一维判什么、不判什么

**判**：每个错误码都有终态归处且**互不冒充**；脱敏包 schema 与 `decision=null` 的约束；摘要（digest）规则；重启/遗留的 `INTERRUPTED` 与 `CANCELLED` 分支；取消的各种竞态；存储与删除的边界。

**不判**：不把错误统一写成"引用不支持"；已恢复的错误仍保留在尝试记录里。

### 6.2 前提

- 术语表 `glossary.md` §1-§5 是状态/阶段/错误码/标签的权威，用例直接读它做对账。
- 时间相关的用例用虚拟时钟，避免真实等待。

### 6.3 步骤

1. 逐个错误码构造终态，断言 `terminal_status()` 与术语表一致；
2. 对脱敏包断言字段集合与 `decision` 为 `null`；
3. 对摘要规则做"应当相同/应当不同"的双向断言；
4. 用虚拟时钟跑重启、取消、超时的竞态。

### 6.4 判据与对应用例

| 编号 | 判据 | 前提 | 步骤 | 对应用例 |
| --- | --- | --- | --- | --- |
| BD-1 | 每个错误码的终态映射与术语表一致 | `glossary.md` 可得 | 遍历枚举对账 | `test_terminal_status_matches_the_glossary_tables`、`test_status_classification_matches_the_documented_upstream_codes` |
| BD-2 | 身份错配必须落 `SOURCE_MISMATCH`，不得被当作"来源不存在"：含 Crossref/PMC DOI 不一致、PLOS 子文章 DOI | 构造子文章 DOI 记录 | 取回并断言阻断码 | `test_doi_mismatch_between_crossref_and_pmc_is_blocked`、`test_a_sub_article_doi_never_stands_in_for_the_article_doi`、`test_a_record_without_its_own_doi_does_not_borrow_a_sub_article_doi`、`test_a_plos_shaped_record_is_no_longer_rejected_as_a_doi_mismatch` |
| BD-3 | 许可未知 / 许可已知但不支持 / 语言不支持 / 内容缺失 / 无来源各走独立码 | 各构造一份记录 | 逐个断言 | `test_unsupported_or_unknown_licenses_are_blocked`、`test_supported_licenses_are_accepted`、`test_non_english_body_is_language_unsupported`、`test_missing_pmc_source_is_source_unavailable`、`test_a_front_matter_only_source_blocks_before_retrieval_and_judgement` |
| BD-4 | DOI 六种分支各有独立结果：格式错、Crossref 404 但机构确认、有效非 Crossref、机构未找到但官方解析成功、官方明确未找到、网络超时 | 六份替身响应 | 逐分支断言 HTTP 与错误码 | `test_doi_normalization_and_validation`、`test_crossref_404_with_agency_confirmed_is_metadata_not_found`、`test_agency_missing_and_resolver_miss_is_doi_unresolvable`、`test_resolver_redirect_without_agency_record_is_metadata_not_found`、`test_pmc_id_conversion_upstream_errors_are_not_source_unavailable`、`test_crossref_auth_failure_is_not_an_invalid_request` |
| BD-5 | 摘录不匹配且修复仍失败 → `QUOTE_MISMATCH`；任一证据无效即阻止确定判断 | 构造定位不到的引文 | 跑 workflow 看终态 | `test_quote_mismatch_after_repair_fails`、`test_quote_error_after_the_single_repair_is_used_reports_quote_mismatch`、`test_evidence_from_a_paragraph_outside_the_context_is_repaired` |
| BD-6 | 脱敏包 schema 2.2 字段与 JSON 形状正确；FAILED/BLOCKED/INTERRUPTED/CANCELLED 的 `decision` 为 `null` | 各终态各一份包 | 校验 schema 与 `decision` | `test_diagnostic_packet_is_redacted_and_export_needs_consent`、`test_a_failed_run_is_redacted_the_same_way`、`test_every_free_text_field_in_the_redacted_packet_is_a_placeholder` |
| BD-7 | usage/模型版本缺失记 `null` 不写零；逐次元数据缺失但路由可靠时保留结论、`accounting=unverified`、展示已记录下界 | 替身不返回 usage | 跑一次读调用账 | `test_a_missing_usage_is_unknown_not_zero`、`test_one_unobserved_attempt_keeps_the_whole_field_unknown`、`test_a_call_without_a_dispatched_attempt_is_unverified`、`test_missing_usage_and_missing_ids_stay_null_rather_than_zero` |
| BD-8 | 摘要规则：键序不影响、空白与数组序影响；运行计数不影响、判据语义与有效配置变化必须影响；旧快照可按引用取回 | 有两份等价/不等价配置 | 双向断言摘要相等与不等 | `test_canonical_json_sorts_keys_and_is_compact`、`test_canonical_digest_rules_from_the_glossary`、`test_canonical_numbers_have_no_exponent_and_normalize_negative_zero`、`test_criteria_reference_is_stable_and_content_addressed`、`test_the_prompt_version_on_calls_is_the_one_the_frozen_snapshot_pins`、`test_the_dispatched_provider_model_is_part_of_the_frozen_digest` |
| BD-9 | 重启发现无取消标记的 `RUNNING` → `INTERRUPTED`（保留诊断、标签为空）；有取消标记 → `CANCELLED`，两分支分开断言 | 造遗留行 | 分别跑结算 | `test_settle_orphaned_running_splits_cancelled_from_interrupted`、`test_a_leftover_running_row_past_its_deadline_settles_as_interrupted`、`test_a_leftover_running_row_without_a_deadline_settles_as_interrupted`、`test_a_cancel_accepted_leftover_settles_as_cancelled`、`test_worker_reports_an_interrupt_and_exits_zero` |
| BD-10 | 取消矩阵：QUEUED/RUNNING、重复取消幂等、取消先于完成、完成先于取消、总超时与取消竞争、迟到响应不覆写终态 | 各时序构造 | 逐时序断言终态与尝试数 | `test_queued_cancel_short_circuits_and_repeats_are_idempotent`、`test_accepted_cancel_blocks_a_later_completion_and_wins`、`test_completion_without_a_cancel_still_lands`、`test_terminal_result_never_overwrites_a_terminal_state`、`test_live_deadline_accepts_cancel_without_false_expiry`、`test_worker_finishes_a_claimed_cancelled_task_as_cancelled` |
| BD-11 | 契约词汇与前端一致：枚举对齐术语表、前端字面量与 Python 常量一致、前端对象形状对齐 OpenAPI、依赖锁与声明闭包一致 | 前端依赖已安装 | 跑形状比对 | `test_enums_match_glossary`、`test_frontend_literals_match_python_contracts`、`test_frontend_object_shapes_match_openapi`、`test_shape_comparison_detects_frontend_drift`、`test_lockfile_matches_declared_dependency_closure` |
| BD-12 | 存储边界：运行中不得删除、来源缓存随最后引用释放、历史倒序、详情字段齐全、终态时间戳成对写入 | 造多任务 | 断言查询结果与时间戳 | `test_delete_refuses_a_running_task`、`test_delete_keeps_a_source_cache_until_its_last_reference_is_gone`、`test_list_orders_by_creation_time_descending`、`test_detail_exposes_the_claim_source_and_run_timing`、`test_every_terminal_path_stamps_updated_at_and_finished_at_together` |
| BD-13 | 多 worker 下独占：同一时刻只有一个任务在跑，并发认领只有一个赢家 | 两个 worker | 同时 claim | `test_a_running_task_blocks_another_claim`、`test_concurrent_claims_produce_exactly_one_winner`、`test_a_second_worker_startup_keeps_a_live_task_running` |

### 6.5 这一维的现状与缺口

- **缺口（明确）**：`test-plan.md:124` 要求「未创建任务的预览错误不得伪造 BLOCKED 任务」。现有用例覆盖了创建冲突不带任务（`test_creation_conflict_needs_no_task_and_task_conflict_requires_state`），但**预览失败不得产生 BLOCKED 任务**这一条没有专门断言。
- **缺口**：`test-plan.md:118` 的「模拟控制失效须停止后续调用，不能按仅缺元数据放行」只被 `test_a_call_without_a_dispatched_attempt_is_unverified` 间接覆盖，没有"控制失效后必须停"的正向断言。

---

## 7. 性能

### 7.1 这一维判什么、不判什么

**判**：单进程、一次一个任务；三档时限（45s 模型尝试 / 15s 来源请求 / 180s 总执行）与剩余时间的截短；单任务测量字段（延迟、逻辑请求数、上游尝试数、token）。

**不判**：不引入 Redis / Locust / JMeter / 分布式压测（`test-plan.md:126`）。

### 7.2 前提

- 用虚拟时钟驱动，避免真实等待 180 秒；只有个别用例走真实本机集成。
- 测量字段从 store 读回，缺失写"未知"不写 0。

### 7.3 步骤

1. 让时钟停在某个相位，发起模型/来源调用，断言单次超时被截短；
2. 耗尽总时限，断言落 `TASK_TIMEOUT` 而不是某次尝试失败；
3. 提交第二个任务，断言它停在 `QUEUED`；
4. 读回测量记录，核对四个字段。

### 7.4 判据与对应用例

| 编号 | 判据 | 前提 | 步骤 | 对应用例 |
| --- | --- | --- | --- | --- |
| PF-1 | 单进程一次只claim一个任务；后提交的停在 `QUEUED`，不另起执行器 | 队列里有两个任务 | 跑 run_once 与 drain 各一次 | `test_one_run_once_claims_at_most_one_task`、`test_the_drain_loop_runs_tasks_one_after_another`、`test_a_task_submitted_while_another_runs_stays_queued`、`test_an_empty_queue_makes_run_once_report_nothing` |
| PF-2 | 总时限从 **claim** 开始计（不含排队），含解析与重试等待；剩余时间会截短单次超时；耗尽后落 `TASK_TIMEOUT` 而不是一次尝试 | 虚拟时钟 | 三个相位各跑一次 | `test_the_task_clock_starts_at_claim_not_at_enqueue`、`test_a_single_model_attempt_is_capped_at_45_seconds`、`test_a_source_request_is_capped_at_15_seconds`、`test_the_remaining_task_time_truncates_a_single_model_attempt`、`test_an_exhausted_task_clock_is_task_timeout_not_an_attempt`、`test_an_exhausted_task_clock_stops_a_source_request` |
| PF-3 | `Retry-After` 大于剩余时间不等待；退避等待可被取消打断 | 时钟剩余不足 | 两种取值各跑一次 | `test_a_source_retry_after_beyond_the_remaining_time_is_not_waited_out`、`test_a_retry_after_within_the_remaining_time_is_waited_out_then_retried`、`test_a_backoff_wait_is_interruptible` |
| PF-4 | 测量记录：逻辑请求数与上游尝试数**分开计**、usage 缺失记未知、多尝试求和、未派发记 `unverified`、排队任务无延迟 | 有完整/缺失 usage 两种替身 | 跑两次读记录 | `test_logical_requests_and_upstream_attempts_are_counted_separately`、`test_a_missing_usage_is_unknown_not_zero`、`test_one_unobserved_attempt_keeps_the_whole_field_unknown`、`test_recorded_usage_is_summed_across_attempts`、`test_a_call_without_a_dispatched_attempt_is_unverified`、`test_the_latency_of_a_claimed_run_is_recorded`、`test_a_queued_task_has_no_latency_and_no_timestamps` |
| PF-5 | 失败必须报告具体测量，不能只记录不判断 | 有时限被触发的任务 | 读记录并断言字段存在 | `test_an_exhausted_task_clock_is_task_timeout_not_an_attempt`、`test_the_latency_of_a_claimed_run_is_recorded` |

### 7.5 这一维的现状与缺口

- **缺口（明确）**：`test-plan.md:125` 的「本机无负载集成检查：取消接口 1 秒内响应、受理后 2 秒内收尾释放 worker、deadline 后 2 秒内收尾」**没有对应用例**。`tests/performance/` 里全部是虚拟时钟断言，没有一条真实计时的响应时限检查。这条目前只能由 `#20` 的手工联调覆盖，**不能写成自动化已验**。

---

## 8. 界面主路径（`tests/e2e/`，不计入七维度）

`test-plan.md:128` 明确：界面主路径放在 `tests/e2e/`，**不替代上面各维的判定**。共 16 条（Playwright），覆盖：

| spec | 条数 | 覆盖 |
| --- | --- | --- |
| `01-shell` | 2 | 空任务库空态并标明真实接口模式；未识别链接被挡回新建 |
| `02-main-path` | 4 | 提交前必须看到来源身份/接收方/数据范围/预算；跑完渲染判断与可定位原文位置；刷新后从本地记录读回；诊断页展示调用账与逐次尝试 |
| `03-cancel` | 1 | 取消运行中与排队中的任务 |
| `04-upstream-timeout` | 1 | 上游超时落成执行失败，并与学术判断区分 |
| `05-diagnostics` | 2 | 脱敏包明示书目未遮盖、语义导出需单独授权；诊断页可按任务标识深链打开 |
| `06-revise-and-delete` | 3 | 修改原句回到新建并创建关联任务；重试用原输入且论断框只读；删除需确认 |
| `07-layout` | 2 | 1440/1024/390 宽度不横向溢出；窄屏证据面板仍可见或可打开 |
| `08-retrieval-form` | 1 | 详情与诊断都标出冻结来源的取回形态 |

运行前置：`npm --prefix tests/e2e ci` + `PAPER_EVIDENCE_E2E_PYTHON=<主树>/backend/.venv/Scripts/python.exe`，且 8000/5173/8765/8001 空闲；约 1.5 分钟。

---

## 9. 附：缺陷归因链路（`test-plan.md` §1，不属于七维度）

`tests/functional/test_triage.py`（20 条）对应 `test-plan.md:31-39` 的「外部测试 Agent」：从诊断包归因「主因在哪一层」，并**只在给了人工答案时才判检索遗漏**。

| 判据 | 对应用例 |
| --- | --- |
| 不给 `--expect-ordinal` 就不判检索遗漏 | `test_without_an_expected_ordinal_the_tool_refuses_to_claim_a_retrieval_miss` |
| 有结论但不引用已召回段 → 归模型选择，不归检索 | `test_a_recalled_paragraph_the_decision_did_not_cite_is_a_model_choice` |
| 召回但没进上下文 → 上下文缺失 | `test_a_recalled_paragraph_left_out_of_context_is_a_context_miss` |
| 被召回且被引用 → 检索链路无缺陷 | `test_a_recalled_and_cited_paragraph_has_no_retrieval_defect` |
| **没有结论时不得声称"被结论引用"** | `test_a_recalled_paragraph_without_a_decision_is_not_called_retrieval_ok` |
| 来源闸门不重复计成工具错误 | `test_a_source_gate_failure_is_not_reported_twice_as_a_tool_error` |
| 干净运行要显式说"无发现"，不能返回空列表 | `test_a_clean_run_says_so_instead_of_returning_an_empty_list` |
| 归因不依赖论断文本 | `test_the_verdict_does_not_depend_on_the_claim_text` |
| 取消的任务不归因成技术故障 | `test_a_cancelled_run_is_not_attributed_to_a_technical_cause` |

---

## 附录 A：文件级归位（保证 433 条无遗漏）

### A.1 按文件

| 文件 | 收集 | 维度 | 备注 |
| --- | --- | --- | --- |
| `functional/test_semantic_acceptance.py` | 19 | 1 | 按 4 来源参数化 |
| `functional/test_claim_inventory.py` | 38 | 1 | 按 4 来源 + 多组夹具参数化 |
| `functional/test_report_metrics.py` | 13 | 1 | 分母口径 |
| `functional/test_live_frozen_sources.py` | 6 | 1 | **全部 skip**（live） |
| `functional/test_live_evidence_context.py` | 7 | 1 | **全部 skip**（live） |
| `functional/test_triage.py` | 20 | §1 归因 | 不计入七维 |
| `tools/test_sources.py` | 44 | 2 / 6 | 身份与许可闸门同时属边界 |
| `tools/test_sdk_gateway.py` | 36 | 2 | |
| `tools/test_checks_api.py` | 31 | 2 | 任务路由与诊断导出 |
| `tools/test_error_handling.py` | 20 | 2 | HTTP 错误信封与校验错误（错误码终态归 6） |
| `tools/test_live_source_contract.py` | 16 | 2 | **全部 skip**（live） |
| `tools/test_api_contract.py` | 10 | 2 | |
| `tools/test_gateway.py` | 10 | 2 | |
| `retrieval/test_query_and_jats.py` | 12 | 3 | |
| `session/test_workflow.py` | 37 | 4 / 3 | 检索两支与预算都在这里 |
| `adversarial/test_observability.py` | 14 | 5 | |
| `adversarial/test_export_boundary.py` | 5 | 5 | |
| `adversarial/test_leakage.py` | 5 | 5 | |
| `adversarial/test_untrusted_input.py` | 5 | 5 | |
| `boundary/test_storage_lifecycle.py` | 20 | 6 | |
| `boundary/test_domain_contract.py` | 17 | 6 | |
| `boundary/test_worker_exclusivity.py` | 10 | 6 | |
| `boundary/test_digest_and_text.py` | 9 | 6 | |
| `boundary/test_frontend_shapes.py` | 6 | 6 | |
| `boundary/test_test_layout.py` | 2 | 6 | 测试布局自检 |
| `performance/test_worker_deadline.py` | 10 | 7 | |
| `performance/test_worker_measurements.py` | 7 | 7 | |
| `performance/test_worker_isolation.py` | 4 | 7 | |
| `e2e/specs/*.spec.ts` | 16 | 界面 | Playwright，不计入 pytest |

### A.2 29 条 skip 的构成（不是被删的用例）

| 文件 | 条数 | 原因 |
| --- | --- | --- |
| `functional/test_live_frozen_sources.py` | 6 | live 上游检查需显式开启，CI 无外网 |
| `functional/test_live_evidence_context.py` | 7 | 同上 |
| `tools/test_live_source_contract.py` | 16 | 同上 |

开启方式：`PAPER_EVIDENCE_LIVE_SOURCES=1`。**未开启时写"通过"是错的**，只能写"未执行"。

---

## 附录 B：未覆盖清单（诚实表）

下面每一条都是 `test-plan.md` 里的**明文判据**。标「已覆盖」的是本轮补上用例、并做过反向对照的；其余仍无断言。列在这里是为了不让它们被通过率掩盖。

| # | 判据出处 | 判据 | 现状 | 处置 |
| --- | --- | --- | --- | --- |
| 1 | `:83` | 多主张输入返回拆分提示，改写或拆分后重新确认提交 | **半覆盖（实现缺口）**：输入页有一条静态提示「多个主张请手动拆分」，但「多主张 → 只说明歧义、不输出确定判断」这条运行时行为不存在——`agents/prompts.py` 全文没有相关约束 | 需产品决定：补提示词（要 bump `PROMPT_VERSION`、旧 `config_digest` 快照会 409），或在文档里降级这一句 |
| 2 | `:83` | 上一条论断不得进入下一条任务（模型上下文不继承） | **已覆盖**：`tests/session/test_workflow.py::test_a_linked_task_never_sees_the_previous_claim` | 已补 |
| 3 | `:72` | unicode61 下中文子词召回盲区 | 无断言 | 待补 `tests/retrieval/`（要先造中文正文夹具） |
| 4 | `:72` | 中文论断→英文正文受支持 | 只有反方向的来源闸门 | 待补跨语言正向用例（下一批） |
| 5 | `:116` | 取消接口 1 秒内响应、受理后 2 秒内收尾、deadline 后 2 秒内收尾 | 全是虚拟时钟 | 归 `#20` 手工联调，执行记录里留条目 |
| 6 | `:47` | 邻段同样支持论断时，不得仅因更换邻段就硬判失败 | 只有「正确结果必须通过」的正对照 | 待补语义验收变体（下一批） |
| 7 | `:106` | 预览错误不得伪造 BLOCKED 任务 | **已覆盖**：`tests/boundary/test_preview_failure.py`（5 个错误码参数化 + 存储为空 + 成功分支反向对照） | 已补 |
| 8 | `:91` | 重试路径也要注入敏感标记 | **已覆盖**：`tests/adversarial/test_retry_leakage.py`（redacted / consented 两向对照） | 已补 |
| 9 | `:103` | 模拟控制失效须停止后续调用 | 只有 `unverified` 的间接覆盖 | 待补「控制失效即停」的正向断言（下一批） |

**行号已订正**：本表原先引用的 `:114` / `:100` / `:125` / `:124` / `:115` / `:118` 与 `test-plan.md` 实际行不对应（该文件一直是 130 行、`多主张` 一直在 `:83`），本轮按判据原文逐条 `grep` 核对后改成 `:83` / `:72` / `:116` / `:106` / `:91` / `:103`。`test-plan.md` 本身**没有被改动**：它的 `:46` 被三处代码/文档按行号引用，插行会错位。

9 条中 **3 条已补自动化用例、1 条半覆盖（实现缺口）、5 条仍待处置**。`#113` 的收口标准是每条都有归属，不是每条都自动化；但「未实现」与「未测」必须分开写——第 1 条是前者，补用例补不出一个不存在的实现。

---

## 附录 C：与 `#93`「备好考卷」的对应

| `#93` 条目 | 本文档的角色 | 状态 |
| --- | --- | --- |
| `#86` 真实来源人工答案 | 第 1 维的判据与用例来源 | **24 条，全部签核**（`#86` 已关闭） |
| 七维度用例清单文档（本文档） | 本体 | 完成 |
| `#20` 联调清单 | 附录 B 的 1/2/5 可由它覆盖 | 4/20 |
| 全部用例执行，留执行记录 | 按维度分节复跑，输出贴到执行记录 | 待跑（10-24） |
| 真实模型跑三项指标 | 第 1 维 + `evaluation.md` §4 | 待跑（10-28） |

---

---

## 附录 D：未在判据表中点名的用例（无孤儿）

判据表点名 210 个用例函数，仓库共 349 个；下面 139 个属**同一判据的补充断言与边界变体**，
为免遗漏逐条列出。它们不单独占用判据行，但都随所属文件一起执行，跑同一维时都会被跑到。

| 文件 | 未点名的用例 |
| --- | --- |
| `tests/adversarial/test_observability.py` | `test_a_missing_observability_recipient_stays_unset`、`test_a_blank_observability_recipient_counts_as_unset`、`test_each_step_becomes_one_span_in_the_task_trace`、`test_the_exporter_speaks_otlp_http_to_the_langfuse_path`、`test_export_off_by_default_builds_no_recorder` |
| `tests/boundary/test_digest_and_text.py` | `test_paragraph_normalization_and_identity`、`test_quote_spans_are_exact_and_can_repeat`、`test_claim_blank_check_uses_a_temporary_copy`、`test_claim_excerpt_is_a_bounded_single_line_display_copy` |
| `tests/boundary/test_domain_contract.py` | `test_module_boundaries_are_importable`、`test_the_decision_prompt_carries_the_label_criteria_not_just_the_names`、`test_the_prompt_examples_are_not_taken_from_the_functional_samples`、`test_worker_entry_drains_an_empty_queue`、`test_worker_entry_reports_a_blocked_queue_instead_of_an_empty_one`、`test_worker_loop_options_come_from_arguments_or_environment`、`test_drain_forever_keeps_polling_and_stops_on_cancellation`、`test_drain_forever_survives_a_failing_iteration`、`test_run_once_settles_a_task_whose_workflow_cannot_be_built`、`test_repository_exposes_conditional_cancel_operations`、`test_default_budgets_match_glossary_and_return_independent_instances` |
| `tests/boundary/test_storage_lifecycle.py` | `test_claimed_deadline_records_a_wall_clock_epoch`、`test_expired_wall_clock_deadline_settles_as_task_timeout`、`test_history_rows_carry_an_excerpt_and_a_timestamp`、`test_finished_at_is_set_when_a_queued_cancel_commits`、`test_source_index_keeps_the_bibliographic_identity`、`test_a_source_row_written_before_authors_existed_still_reads`、`test_a_repeated_request_id_is_rejected_instead_of_overwriting_the_ledger`、`test_opening_an_older_database_adds_the_new_columns_and_keeps_rows` |
| `tests/boundary/test_test_layout.py` | `test_the_detector_recognises_bare_conftest_imports`、`test_no_test_module_imports_conftest_by_bare_name` |
| `tests/boundary/test_worker_exclusivity.py` | `test_a_refused_run_once_leaves_the_live_task_and_the_queue_alone`、`test_a_refused_claim_reports_the_blocking_running_task`、`test_settling_a_leftover_does_not_claim_it_back`、`test_the_queue_resumes_after_a_crash_leftover_is_settled` |
| `tests/functional/test_claim_inventory.py` | `test_the_committed_inventory_is_structurally_valid`、`test_the_source_unverifiable_label_is_not_a_judgement_label`、`test_every_judgement_label_is_accepted`、`test_an_insufficient_claim_may_cite_a_fragment_but_is_flagged_for_review`、`test_an_unknown_field_is_reported_but_does_not_fail_the_record`、`test_offline_a_complete_preview_is_a_complete_check`、`test_the_directory_option_keeps_its_old_name_as_an_alias`、`test_a_drifted_paragraph_hash_is_reported_as_drift`、`test_coverage_counts_candidates_and_says_none_are_signed`、`test_a_missing_review_warns_while_the_key_is_being_written`、`test_the_gate_refuses_an_unsigned_claim`、`test_a_present_review_is_shape_checked`、`test_review_gaps_names_every_unsigned_or_disputed_entry`、`test_empty_claims_are_reported_as_incomplete_not_as_passing`、`test_the_checker_reads_the_files_it_ships_with` |
| `tests/functional/test_live_evidence_context.py` | `test_a_real_frozen_source_has_enough_paragraphs_to_expand`、`test_the_scripted_task_completed_and_cited_a_real_paragraph`、`test_evidence_context_marks_the_cited_anchor`、`test_the_http_endpoint_returns_the_same_neighbours` |
| `tests/functional/test_report_metrics.py` | `test_the_identity_holds_and_every_slot_lands_in_exactly_one_bucket`、`test_a_zero_over_a_non_empty_denominator_is_a_real_zero`、`test_the_refusal_error_rate_is_na_when_the_refusal_set_never_completed`、`test_the_report_never_hardcodes_a_sample_count`、`test_the_macro_f1_label_list_keeps_the_definition_order`、`test_the_report_carries_no_commit_dependent_field`、`test_the_sample_fingerprint_tracks_the_sample_set` |
| `tests/functional/test_triage.py` | `test_the_fixture_is_a_real_completed_packet`、`test_a_source_gate_never_reaches_the_model`、`test_a_rate_limited_attempt_is_attributed_to_the_upstream`、`test_a_quote_mismatch_is_named_with_its_request_and_repair`、`test_an_explicit_retrieval_error_is_reported_as_such`、`test_an_empty_candidate_set_alone_is_not_called_a_retrieval_miss`、`test_a_label_difference_with_a_clean_pipeline_is_a_criteria_gap`、`test_both_human_answers_together_keep_the_divergence_primary_on_a_clean_pipeline`、`test_both_human_answers_with_a_technical_error_demote_the_divergence`、`test_the_cli_reads_a_packet_file_and_prints_the_primary_cause`、`test_the_cli_refuses_a_malformed_packet` |
| `tests/performance/test_worker_deadline.py` | `test_the_remaining_task_time_truncates_a_source_request` |
| `tests/retrieval/test_query_and_jats.py` | `test_parse_jats_rejects_unparsable_content` |
| `tests/session/test_workflow.py` | `test_a_quote_repair_points_at_the_first_round_decision`、`test_upstream_failure_records_an_attempt_and_fails`、`test_source_block_is_a_blocked_task_with_the_compatible_label`、`test_a_blocked_front_matter_source_keeps_its_retrieval_form`、`test_unparsable_repair_of_a_retrieve_action_fails_cleanly`、`test_retrieve_without_queries_or_neighbours_is_repaired`、`test_decision_prompt_declares_the_array_fields_and_a_minimal_shape`、`test_repair_note_names_every_decision_field_that_broke_the_contract`、`test_repair_note_locates_a_malformed_retrieve_payload`、`test_decision_prompt_requires_the_candidate_id_to_be_copied_verbatim`、`test_an_id_that_lost_the_p_prefix_is_repaired_with_the_candidate_id`、`test_a_bracketed_id_is_repaired_with_the_unwrapped_candidate_id` |
| `tests/tools/test_api_contract.py` | `test_documented_routes_have_typed_openapi_contracts`、`test_response_comparison_detects_drift_in_both_directions`、`test_no_route_declares_a_pending_response`、`test_health_is_live`、`test_invalid_requests_use_the_api_error_envelope` |
| `tests/tools/test_checks_api.py` | `test_run_config_exposes_the_frozen_digest`、`test_create_then_read_detail_and_history`、`test_cancel_queued_then_repeat_and_unknown`、`test_retry_requires_a_terminal_task_and_links_the_original`、`test_delete_only_terminal_tasks_and_reports_the_cloud_boundary`、`test_feedback_is_stored_separately`、`test_diagnostic_export_needs_a_configured_diagnostic_recipient`、`test_diagnostic_export_accepts_only_the_observation_recipient`、`test_history_and_detail_expose_the_claim_bibliography_and_timing`、`test_history_is_filterable_and_keeps_the_claim_excerpt`、`test_the_input_route_returns_exactly_what_was_submitted`、`test_evidence_context_reads_the_frozen_paragraphs_and_their_neighbours`、`test_evidence_context_ordinals_tell_a_far_anchor_from_a_neighbour`、`test_evidence_context_is_empty_until_a_source_is_frozen`、`test_a_frozen_digest_stops_being_accepted_once_the_effective_config_changes`、`test_diagnostic_export_rejects_a_blank_recipient_and_normalizes_spacing`、`test_recipient_configuration_is_trimmed`、`test_blank_recipient_configuration_counts_as_unset`、`test_the_in_process_sdk_is_the_default_transport`、`test_an_unknown_transport_falls_back_to_the_default`、`test_the_snapshot_records_which_kind_of_endpoint_is_reached`、`test_the_transport_is_part_of_the_frozen_digest` |
| `tests/tools/test_error_handling.py` | `test_preview_contract_errors_keep_machine_readable_codes`、`test_unmapped_contract_errors_are_not_reclassified`、`test_framework_http_errors_preserve_headers_and_log_only_safe_structure`、`test_validation_errors_expose_locations_without_input_values`、`test_validation_errors_locate_query_fields_and_array_indices` |
| `tests/tools/test_live_source_contract.py` | `test_pmc_id_conversion_resolves_a_real_doi_to_its_pmcid`、`test_the_full_text_prefix_serves_a_body`、`test_the_front_matter_prefix_serves_no_body`、`test_a_frozen_record_indexes_more_paragraphs_than_its_front_matter`、`test_a_fetched_record_is_english_cc_by_full_text`、`test_a_sources_frozen_identity_repeats_across_two_fetches` |
| `tests/tools/test_sdk_gateway.py` | `test_a_timeout_is_not_read_as_a_connection_failure`、`test_every_litellm_failure_class_is_either_mapped_or_deliberately_not`、`test_a_provider_that_refuses_the_connection_is_an_upstream_outage`、`test_a_recovered_attempt_succeeds_with_the_first_failure_still_recorded`、`test_a_retry_without_retry_after_waits_the_documented_minimum`、`test_a_failure_the_sdk_does_not_own_propagates_unchanged`、`test_a_completion_without_a_choice_is_an_invalid_request`、`test_the_module_keeps_the_logging_rules_off_by_default` |
| `tests/tools/test_sources.py` | `test_timeouts_are_timeouts_and_404_is_not_one`、`test_a_transient_failure_without_retry_after_still_waits`、`test_a_retry_after_header_still_wins_over_the_default_backoff`、`test_a_backoff_longer_than_the_remaining_budget_does_not_burn_it`、`test_resolve_returns_a_read_only_preview`、`test_fetch_returns_a_licensed_snapshot_with_a_version_hash`、`test_stable_identifiers_survive_a_second_fetch_of_the_same_record`、`test_pmc_oai_request_prefers_the_full_text_metadata_prefix` |

若某条判据只有附录 D 里的用例支撑，说明该判据在判据表里被合并描述了；改动那些用例时，先回判据表确认覆盖哪一条。

---

*本文档的判据全部引自 `docs/test-plan.md`；用例名与条数为 2026-10-21 在 `main = 7104451` 上实测。改动用例后请同步更新本文档的收集数与附录 A。*
