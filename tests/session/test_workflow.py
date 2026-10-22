"""Bounded multi-step workflow: budgets, repair, cancellation and terminals."""

import asyncio
import json
import time
from dataclasses import replace

import pytest

from paper_evidence.agents.output import OutputError, parse_decision_output
from paper_evidence.agents.prompts import PaperPromptBuilder
from paper_evidence.config import Settings
from paper_evidence.domain import ContractError, ErrorCode, Stage, TaskStatus
from paper_evidence.domain.contracts import (
    Limits,
    ModelAttempt,
    ModelCall,
    RunConfigSnapshot,
    SourcePreview,
    SourceRecord,
    default_timeouts,
)
from paper_evidence.domain.records import ModelReply, SourceSnapshot, TaskInput
from paper_evidence.domain.rules import criteria_reference
from paper_evidence.graph.workflow import BoundedWorkflow
from paper_evidence.models.recording import AttemptCancelled
from paper_evidence.retrieval.local import StoreRetriever
from paper_evidence.storage.sqlite import SqliteStore

VERSION_HASH = "a" * 64
PID1 = f"p:PMC123:{VERSION_HASH}:jats-0.1.0:1"
PID2 = f"p:PMC123:{VERSION_HASH}:jats-0.1.0:2"
QUOTE1 = "The treatment reduced mortality by 20 percent."
QUOTE2 = "No effect was observed in the control group."
JATS = f"""<?xml version="1.0" encoding="UTF-8"?>
<article xml:lang="en"><front><article-meta/></front><body>
<sec id="s1"><title>Results</title>
<p id="n1">{QUOTE1}</p>
<p id="n2">{QUOTE2}</p>
</sec></body></article>
""".encode("utf-8")


def final_json(quote=QUOTE1, label="支持", paragraph_id=PID1, evidence=None, **overrides):
    """A legal final response, or the same shape with named decision fields replaced."""

    items = [{"paragraph_id": paragraph_id, "quote": quote}] if evidence is None else evidence
    decision = {
        "label": label, "rationale": "r", "supported_parts": [], "scope_differences": [],
        "limitations": [], "evidence": items,
    }
    decision.update(overrides)
    return json.dumps({"action": "final", "decision": decision}, ensure_ascii=False)


def neighbour_only_final(label="支持", paragraph_id=PID1):
    return final_json(label=label, paragraph_id=paragraph_id, evidence=[])


QUERIES = '{"queries": ["mortality"]}'
RETRIEVE = '{"action": "retrieve", "queries": ["mortality"], "neighbor_paragraph_ids": []}'


class FakeResolver:
    def __init__(self, error=None):
        self.error = error

    async def resolve(self, doi, deadline=None):
        if self.error:
            raise self.error
        return SourcePreview(doi=doi, title="Demo", authors=["A"], year=2026)


class FakeFulltext:
    def __init__(self, error=None, retrieval_form="full_text"):
        self.error = error
        self.retrieval_form = retrieval_form

    async def fetch(self, doi, deadline):
        if self.error:
            raise self.error
        record = SourceRecord(title="Demo", authors=["Ada Lovelace"], year=2026, doi=doi, pmcid="PMC123",
                              license="CC BY", version="1", access_url="https://example.org/a",
                              retrieved_at="2026-10-01T00:00:00+00:00", version_hash=VERSION_HASH,
                              retrieval_form=self.retrieval_form)
        return SourceSnapshot(source_id=f"PMC123:{VERSION_HASH}", metadata=record, jats_bytes=JATS)


class FakeGateway:
    """Returns canned responses in order and records the logical requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, request_id, prompt, deadline, *, purpose, round_index, prompt_version="",
                       context_paragraph_ids=None, repairs_request_id=None):
        self.calls.append({"request_id": request_id, "purpose": purpose, "round": round_index,
                           "prompt": prompt})
        item = self.responses.pop(0)
        failed = isinstance(item, Exception)
        attempt = ModelAttempt(
            attempt_id=f"{request_id}:1", attempt_index=1, span_id="s", gateway_request_id=None,
            upstream_response_id=None, configured_model="m", provider_model="p", deployment_id="d",
            recipient="Agnes",
            response_model=None if failed else "agnes", verified_model_version=None, recovery_kind="none",
            recovery_reason=None, status="error" if failed else "success",
            error_code=item.error_code if failed else None, duration_ms=5, usage=None,
        )
        call = ModelCall(request_id=request_id, purpose=purpose, round=round_index, model_alias="paper-default",
                         prompt_version=prompt_version, params_digest="d",
                         context_paragraph_ids=list(context_paragraph_ids or []),
                         repairs_request_id=repairs_request_id, attempts=[attempt])
        if failed:
            from paper_evidence.models.gateway import ModelFailure

            raise ModelFailure(item.error_code, call, "boom")
        return ModelReply(text=item, call=call)


class CancellingGateway(FakeGateway):
    """Accepts a cancel as the canned final-decision response is returned.

    This reproduces the review's window exactly: the last ``_check_cancel`` (at
    the start of ``_main_request``) already passed, the cancel then lands while
    the final model call is in flight, and the terminal write follows. The
    cancel must win (测试方案「取消先于完成」).
    """

    def __init__(self, responses, store, task_id, *, purpose="decision", round_index=0, when="after"):
        super().__init__(responses)
        self._store = store
        self._task_id = task_id
        self._purpose = purpose
        self._round = round_index
        self._when = when

    async def complete(self, request_id, prompt, deadline, *, purpose, round_index, prompt_version="",
                       context_paragraph_ids=None, repairs_request_id=None):
        target = purpose == self._purpose and round_index == self._round
        if target and self._when == "before":
            # Cancel lands inside the model call, after the request's own
            # `_check_cancel` already passed.
            self._store.request_cancel(self._task_id)
        reply = await super().complete(
            request_id, prompt, deadline, purpose=purpose, round_index=round_index,
            prompt_version=prompt_version, context_paragraph_ids=context_paragraph_ids,
            repairs_request_id=repairs_request_id,
        )
        if target and self._when == "after":
            self._store.request_cancel(self._task_id)
        return reply


class SlowGateway(FakeGateway):
    """Holds each request open, so a cancel can land while it is in flight.

    Mirrors the transports' abort path: a request already dispatched stays in the
    ledger as a ``cancelled`` attempt with unknown usage instead of disappearing
    (Issue #113). ``started`` counts dispatches, so a test can tell a request that
    was never sent from one that was aborted.
    """

    def __init__(self, seconds, responses):
        super().__init__(responses)
        self._seconds = seconds
        self.started = []

    async def complete(self, request_id, prompt, deadline, *, purpose, round_index, prompt_version="",
                       context_paragraph_ids=None, repairs_request_id=None):
        self.started.append(request_id)
        try:
            await asyncio.sleep(self._seconds)
        except asyncio.CancelledError:
            raise AttemptCancelled(ModelCall(
                request_id=request_id, purpose=purpose, round=round_index, model_alias="paper-default",
                prompt_version=prompt_version, params_digest="d",
                context_paragraph_ids=list(context_paragraph_ids or []),
                repairs_request_id=repairs_request_id,
                attempts=[ModelAttempt(
                    attempt_id=f"{request_id}:1", attempt_index=1, span_id="s", gateway_request_id=None,
                    upstream_response_id=None, configured_model="m", provider_model="p", deployment_id="d",
                    recipient="Agnes", response_model=None, verified_model_version=None, recovery_kind="none",
                    recovery_reason=None, status="cancelled", error_code=None, duration_ms=5, usage=None,
                )],
            )) from None
        return await super().complete(
            request_id, prompt, deadline, purpose=purpose, round_index=round_index,
            prompt_version=prompt_version, context_paragraph_ids=context_paragraph_ids,
            repairs_request_id=repairs_request_id,
        )


class UnaccountedGateway(FakeGateway):
    """Answers correctly but reports no dispatched attempt for the dispatch.

    This is what losing the routing/budget control looks like from the workflow
    side: the text arrives, the ledger entry does not. It must stop the task
    instead of passing as「只是缺 usage」（测试方案「边界与异常」, Issue #113）.
    """

    async def complete(self, request_id, prompt, deadline, *, purpose, round_index, prompt_version="",
                       context_paragraph_ids=None, repairs_request_id=None):
        reply = await super().complete(
            request_id, prompt, deadline, purpose=purpose, round_index=round_index,
            prompt_version=prompt_version, context_paragraph_ids=context_paragraph_ids,
            repairs_request_id=repairs_request_id,
        )
        return ModelReply(text=reply.text, call=reply.call.model_copy(update={"attempts": []}))


class SlowResolver(FakeResolver):
    """A source identity call that takes long enough to be cancelled in flight."""

    def __init__(self, seconds):
        super().__init__()
        self._seconds = seconds
        self.accepted = 0

    async def resolve(self, doi, deadline=None):
        self.accepted += 1
        await asyncio.sleep(self._seconds)
        return SourcePreview(doi=doi, title="Demo", authors=["A"], year=2026)


@pytest.fixture
def settings(tmp_path):
    return replace(Settings.from_env(), data_dir=tmp_path, contact_email="")


@pytest.fixture
def store(tmp_path):
    db = SqliteStore(tmp_path / "workflow.sqlite3")
    yield db
    db.close()


def make_task(store, settings, claim="The treatment reduced mortality."):
    task = TaskInput(id="t1", claim=claim, doi="10.1000/xyz", config_digest="d", authorized_recipients=("Agnes",))
    run_config = RunConfigSnapshot(profile="daily", config_digest="d", snapshot_ref="r",
                                   authorized_recipients=["Agnes"], limits=settings.limits,
                                   timeouts=settings.timeouts, observability=settings.observability)
    store.create(task, run_config, criteria_reference("rev"))
    return task


def run(store, settings, responses, *, resolver=None, fulltext=None, claim="The treatment reduced mortality.",
        deadline=None, limits=None, gateway=None):
    if limits is not None:
        settings = replace(settings, limits=limits)
    gateway = gateway if gateway is not None else FakeGateway(responses)
    workflow = BoundedWorkflow(
        store=store, resolver=resolver or FakeResolver(), fulltext=fulltext or FakeFulltext(),
        retriever=StoreRetriever(store, settings.retrieval_context_limit),
        prompts=PaperPromptBuilder(), gateway=gateway, settings=settings,
    )
    task = make_task(store, settings, claim=claim)
    end = deadline if deadline is not None else time.monotonic() + 180
    detail = asyncio.run(workflow.run(task, end))
    return detail, gateway


def test_happy_path_publishes_a_supported_label_with_locatable_evidence(store, settings):
    detail, gateway = run(store, settings, [QUERIES, final_json()])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.label == "支持"
    assert detail.error_code is None
    assert detail.decision is not None
    assert detail.decision.evidence[0].validation == "pass"
    assert detail.decision.evidence[0].paragraph_id == PID1
    assert detail.accounting.main_requests_used == 2
    assert detail.accounting.upstream_attempts_used == 2
    assert detail.accounting.verification == "verified"
    assert [call["purpose"] for call in gateway.calls] == ["query_generation", "decision"]
    # Execution spans include the source and retrieval stages.
    stages = {event.stage.value for event in store.execution("t1")}
    assert {"source_identity", "fetch", "query_generation", "retrieval", "decision"} <= stages


def test_first_empty_retrieval_requests_a_supplemental_round(store, settings):
    detail, gateway = run(store, settings, ['{"queries": ["zzzz"]}', RETRIEVE, final_json()])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.label == "支持"
    assert detail.accounting.supplemental_rounds_used == 1
    assert [call["round"] for call in gateway.calls] == [0, 0, 1]


def test_two_empty_rounds_yield_insufficient_evidence(store, settings):
    detail, _ = run(store, settings, ['{"queries": ["zzzz"]}', '{"action": "retrieve", "queries": ["yyyy"]}'])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.label == "证据不足"
    assert detail.error_code is ErrorCode.RETRIEVAL_EMPTY
    assert detail.decision is not None and detail.decision.evidence == []


def test_final_on_empty_retrieval_is_repaired_into_a_supplemental_query(store, settings):
    # Request 2 wrongly returns final; the repair turns it into a retrieve.
    detail, gateway = run(store, settings, ['{"queries": ["zzzz"]}', final_json(), RETRIEVE, final_json()])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.accounting.repair_requests_used == 1
    assert gateway.calls[2]["purpose"] == "output_repair"


def test_unlocatable_quote_is_repaired_once_then_published(store, settings):
    detail, gateway = run(store, settings, [QUERIES, final_json(quote="A rewritten sentence."), final_json()])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.label == "支持"
    assert detail.accounting.repair_requests_used == 1
    assert detail.accounting.main_requests_used == 2
    assert gateway.calls[-1]["purpose"] == "output_repair"


def test_quote_mismatch_after_repair_fails(store, settings):
    detail, _ = run(store, settings, [QUERIES, final_json(quote="wrong one"), final_json(quote="wrong two")])
    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.QUOTE_MISMATCH
    assert detail.label is None and detail.decision is None


# ------------------------------------------- repair round attribution (#70)


def assert_repairs_point_at_recorded_requests(calls):
    """Every repair pointer names a request that exists in the same ledger.

    调用账的这条边是诊断包与外部评审的归因依据；反向指针指向不存在的请求时，
    按它反查会查空或误配到另一条任务里同名的真实请求（Issue #70）。
    """

    ids = {call.request_id for call in calls}
    for call in calls:
        if call.repairs_request_id is not None:
            assert call.repairs_request_id in ids


def test_a_quote_repair_points_at_the_first_round_decision(store, settings):
    """首轮直接 final 的任务：引文校验修的是 decision:0，不是从未存在的 decision:1。

    旧实现把 `_validate` 的修复硬编码成 round_index=1，这里只有一次 decision
    请求（round 0），记录却写成 `t1:decision:1`；`docs/semantic-acceptance-live.md`
    的三轮真实运行里有 7 处这种记录。
    """

    detail, _ = run(store, settings, [QUERIES, final_json(quote="A rewritten sentence."), final_json()])
    assert detail.status is TaskStatus.COMPLETED

    calls = store.model_calls("t1")
    assert [call.request_id for call in calls] == ["t1:query_generation:0", "t1:decision:0",
                                                   "t1:output_repair:1"]
    repair = calls[-1]
    assert repair.purpose == "output_repair"
    assert repair.round == 0
    assert repair.repairs_request_id == "t1:decision:0"
    assert_repairs_point_at_recorded_requests(calls)


def test_a_quote_repair_after_a_supplemental_round_points_at_decision_one(store, settings):
    """发生过补读的任务：被修的是第 1 轮的 decision，修复记 round=1 并指向它。"""

    detail, _ = run(store, settings, ['{"queries": ["zzzz"]}', RETRIEVE, final_json(quote="wrong"),
                                      final_json()])
    assert detail.status is TaskStatus.COMPLETED

    calls = store.model_calls("t1")
    assert [call.request_id for call in calls] == ["t1:query_generation:0", "t1:decision:0",
                                                   "t1:decision:1", "t1:output_repair:1"]
    repair = calls[-1]
    assert repair.round == 1
    assert repair.repairs_request_id == "t1:decision:1"
    assert_repairs_point_at_recorded_requests(calls)


def test_two_repairs_of_one_decision_keep_two_distinct_request_ids(store, settings):
    """同一个 decision:0 被修两次时，两条记录都要留下 —— 主键不能相撞。

    解析失败先用掉一次修复，引文校验失败再用一次（额度调大到 2 才可达）。两次修的
    是同一个 (purpose, round)，所以判别式不能取轮次：那样两条都叫
    `t1:output_repair:0`，而 `model_calls` 的主键是 (task_id, request_id)，
    后写的会覆盖先写的，调用账静默少一条（Issue #70 的附带风险）。
    """

    limits = Limits(main_requests=3, repair_requests=2, attempts_per_request=2, supplemental_rounds=1)
    detail, _ = run(store, settings, [QUERIES, '{"action": "final"}',
                                      final_json(paragraph_id="not-a-candidate-id"), final_json()],
                    limits=limits)

    assert detail.status is TaskStatus.COMPLETED
    assert detail.accounting.repair_requests_used == 2
    calls = store.model_calls("t1")
    assert [call.purpose for call in calls] == ["query_generation", "decision", "output_repair",
                                                "output_repair"]
    repairs = calls[2:]
    assert [call.request_id for call in repairs] == ["t1:output_repair:1", "t1:output_repair:2"]
    assert [call.round for call in repairs] == [0, 0]
    assert [call.repairs_request_id for call in repairs] == ["t1:decision:0", "t1:decision:0"]
    assert_repairs_point_at_recorded_requests(calls)


def test_budget_exhaustion_fails_before_dispatch(store, settings):
    detail, gateway = run(store, settings, [QUERIES, final_json()],
                          limits=Limits(main_requests=1, repair_requests=1, attempts_per_request=2,
                                        supplemental_rounds=1))
    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.BUDGET_EXCEEDED
    assert len(gateway.calls) == 1


def test_upstream_failure_records_an_attempt_and_fails(store, settings):
    detail, _ = run(store, settings, [ContractError(ErrorCode.UPSTREAM_TIMEOUT, "timeout")])
    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.UPSTREAM_TIMEOUT
    calls = store.model_calls("t1")
    assert calls[0].attempts[0].status == "error"
    assert detail.accounting.upstream_attempts_used == 1
    assert detail.accounting.verification == "verified"


def test_source_block_is_a_blocked_task_with_the_compatible_label(store, settings):
    detail, _ = run(store, settings, [], fulltext=FakeFulltext(error=ContractError(ErrorCode.SOURCE_UNAVAILABLE, "none")))
    assert detail.status is TaskStatus.BLOCKED
    assert detail.label == "无法核验来源"
    assert detail.error_code is ErrorCode.SOURCE_UNAVAILABLE
    assert detail.decision is None


def test_a_front_matter_only_source_blocks_before_retrieval_and_judgement(store, settings):
    """只取回到题录+摘要时阻断，不进检索、不进判定（Issue #28 方案 A）。

    ``pmc_fm`` 只有题录、摘要与许可，没有 ``<body>``；据摘要判「不支持」正是产品需求
    明令禁止的负例。判据取「**一条模型请求都没发**」，而不是「最终标签恰好是证据不足」：
    后者与被攻破的实现无法区分，因为摘要里搜不到证据也会落成证据不足。

    这个替身故意让 ``jats_bytes`` 仍带完整 ``<body>``，只改记录的取回形态：守卫要看的是
    **这次请求实际拿到什么**（``retrieval_form``），不能由解析结果反推——短正文与仅题录
    的记录解析后长得一样（#60 同一条理由）。
    """

    detail, gateway = run(store, settings, [QUERIES, final_json()],
                          fulltext=FakeFulltext(retrieval_form="front_matter"))

    assert detail.status is TaskStatus.BLOCKED
    assert detail.error_code is ErrorCode.CONTENT_INCOMPLETE
    assert detail.label == "无法核验来源"
    assert detail.decision is None
    assert detail.stage is Stage.FETCH
    assert gateway.calls == [], "阻断必须发生在生成检索词之前"


def test_a_blocked_front_matter_source_keeps_its_retrieval_form(store, settings):
    """阻断也要先把来源冻结下来：详情页据 ``retrieval_form`` 说明「仅题录+摘要」（#92）。

    先冻结、后拒绝判定是有意为之：若在连接器里直接抛错，来源不落在任何任务上，
    界面与诊断包就没有字段可读，只剩一句错误文案。
    """

    detail, _ = run(store, settings, [QUERIES, final_json()],
                    fulltext=FakeFulltext(retrieval_form="front_matter"))

    assert detail.source is not None, "来源必须随任务落库，否则取回形态无处可读"
    assert detail.source.retrieval_form == "front_matter"
    assert detail.source.version_hash == VERSION_HASH, "冻结的仍是这个版本，不是这次请求"
    steps = store.execution("t1")
    assert (steps[-1].stage, steps[-1].tool, steps[-1].status) == (
        Stage.FETCH, "retrieval_form_gate", "error")


def test_total_deadline_fails_as_task_timeout(store, settings):
    detail, _ = run(store, settings, [], deadline=time.monotonic() - 1)
    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.TASK_TIMEOUT


def test_accepted_cancel_wins_over_workflow_result(store, settings):
    settings = replace(settings, timeouts=default_timeouts())
    gateway = FakeGateway([QUERIES, final_json()])
    workflow = BoundedWorkflow(
        store=store, resolver=FakeResolver(), fulltext=FakeFulltext(),
        retriever=StoreRetriever(store, settings.retrieval_context_limit),
        prompts=PaperPromptBuilder(), gateway=gateway, settings=settings,
    )
    task = make_task(store, settings)
    store.request_cancel(task.id)  # QUEUED -> CANCELLED before the worker claims it
    detail = asyncio.run(workflow.run(task, time.monotonic() + 180))
    assert detail.status is TaskStatus.CANCELLED
    assert detail.label is None and detail.decision is None
    assert gateway.calls == []


def test_a_cancel_during_an_in_flight_model_call_settles_within_two_seconds(store, settings):
    """受理取消后 2 秒内收尾释放 worker，且这次已派发的请求仍留在调用账里。

    只在阶段边界查取消标记时，要等这次 45 秒的调用返回才收尾（Issue #113 实测
    4.7 秒/5 秒的替身）。收尾快不等于账目干净：请求已经发出去，费用未知要写进
    调用账（status=cancelled、usage=null），不能被读成「什么都没发」。
    """

    gateway = SlowGateway(5.0, [QUERIES, final_json()])
    workflow = BoundedWorkflow(
        store=store, resolver=FakeResolver(), fulltext=FakeFulltext(),
        retriever=StoreRetriever(store, settings.retrieval_context_limit),
        prompts=PaperPromptBuilder(), gateway=gateway, settings=settings,
    )
    task = make_task(store, settings)

    async def scenario():
        pending = asyncio.ensure_future(workflow.run(task, time.monotonic() + 180))
        while not gateway.started:
            await asyncio.sleep(0.01)
        store.request_cancel(task.id)
        accepted = time.monotonic()
        return await pending, time.monotonic() - accepted

    detail, drained = asyncio.run(scenario())

    assert drained < 2.0, f"受理后 {drained:.2f} 秒才收尾，超过 2 秒预算"
    assert detail.status is TaskStatus.CANCELLED
    assert detail.label is None and detail.decision is None
    assert gateway.started == ["t1:query_generation:0"], "取消受理后不得再派发新请求"
    calls = store.model_calls(task.id)
    assert [(call.request_id, [item.status for item in call.attempts]) for call in calls] == [
        ("t1:query_generation:0", ["cancelled"])]
    assert calls[0].attempts[0].usage is None, "被打断的这次调用费用未知，不能补零"
    assert detail.accounting.verification == "verified", "记录在、usage 缺：这不是调用账缺失"
    assert detail.accounting.upstream_attempts_used == 1
    assert (Stage.QUERY_GENERATION, "model_gateway", "cancelled") in {
        (event.stage, event.tool, event.status) for event in store.execution(task.id)}


def test_a_cancel_during_an_in_flight_source_request_stops_before_the_timeout(store, settings):
    """来源请求在途时受理取消同样要立刻收尾，而不是等 15 秒的来源超时。"""

    resolver = SlowResolver(5.0)
    gateway = FakeGateway([QUERIES, final_json()])
    workflow = BoundedWorkflow(
        store=store, resolver=resolver, fulltext=FakeFulltext(),
        retriever=StoreRetriever(store, settings.retrieval_context_limit),
        prompts=PaperPromptBuilder(), gateway=gateway, settings=settings,
    )
    task = make_task(store, settings)

    async def scenario():
        pending = asyncio.ensure_future(workflow.run(task, time.monotonic() + 180))
        while not resolver.accepted:
            await asyncio.sleep(0.01)
        store.request_cancel(task.id)
        accepted = time.monotonic()
        return await pending, time.monotonic() - accepted

    detail, drained = asyncio.run(scenario())

    assert drained < 2.0, f"受理后 {drained:.2f} 秒才收尾，超过 2 秒预算"
    assert detail.status is TaskStatus.CANCELLED
    assert gateway.calls == [], "来源都没取到，不应有模型请求"
    assert detail.source is None
    assert (Stage.SOURCE_IDENTITY, "source_resolver", "cancelled") in {
        (event.stage, event.tool, event.status) for event in store.execution(task.id)}


def test_a_dispatch_the_control_plane_did_not_account_for_stops_the_task(store, settings):
    """控制面没回报这次派发就不能继续派发，而不是当成「只是缺 usage」放行。

    「逐次元数据缺失」的形态是记录在、usage 为空（结果可保留，标 unverified）；
    记录整条没有才是控制失效——继续调用就是在无法计数的通道上花钱。
    """

    gateway = UnaccountedGateway([QUERIES, final_json()])
    detail, gateway = run(store, settings, [], gateway=gateway)

    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.UPSTREAM_UNAVAILABLE
    assert detail.label is None and detail.decision is None
    assert len(gateway.calls) == 1, "第一次派发没有账目，就不该有第二次"
    assert detail.accounting.verification == "unverified"
    assert detail.accounting.reason == "attempt_records_missing"
    assert detail.accounting.observed_upstream_attempts == 0
    assert detail.accounting.upstream_attempts_used is None


def test_missing_usage_alone_does_not_make_the_ledger_incomplete(store, settings):
    """反例：usage 全空但每次派发都有尝试记录时，账仍是完整的（不能误标缺失）。"""

    detail, _ = run(store, settings, [QUERIES, final_json()])

    assert detail.status is TaskStatus.COMPLETED
    assert detail.accounting.verification == "verified"
    assert detail.accounting.upstream_attempts_used == 2
    assert [item.usage for call in store.model_calls("t1") for item in call.attempts] == [None, None]


# ------------------------------------------------- review regression coverage


def test_definitive_label_without_evidence_is_repaired_then_published(store, settings):
    """支持/部分支持/相矛盾 必须有摘录，否则不能以 COMPLETED+pass 发布。"""

    detail, gateway = run(store, settings, [QUERIES, neighbour_only_final(), final_json()])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.label == "支持"
    assert detail.decision.evidence != []
    assert detail.accounting.repair_requests_used == 1
    assert gateway.calls[2]["purpose"] == "output_repair"


def test_definitive_label_still_without_evidence_fails_as_quote_mismatch(store, settings):
    detail, _ = run(store, settings, [QUERIES, neighbour_only_final(), neighbour_only_final()])
    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.QUOTE_MISMATCH
    assert detail.label is None and detail.decision is None


def test_insufficient_evidence_may_publish_without_evidence(store, settings):
    detail, _ = run(store, settings, [QUERIES, neighbour_only_final(label="证据不足")])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.label == "证据不足"
    assert detail.decision.evidence == []
    assert detail.accounting.repair_requests_used == 0


def test_unparsable_repair_output_fails_as_model_invalid_output(store, settings):
    """修复输出无法解析时必须报 MODEL_INVALID_OUTPUT，不能抛 AssertionError。"""

    detail, _ = run(store, settings, [QUERIES, final_json(quote="wrong one"), "not json at all"])
    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.MODEL_INVALID_OUTPUT
    assert detail.label is None and detail.decision is None


def test_unparsable_repair_of_a_retrieve_action_fails_cleanly(store, settings):
    # Request 3 must not re-request a supplement; the repair is unparsable.
    detail, gateway = run(store, settings, [QUERIES, RETRIEVE, RETRIEVE, "still not json"])
    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.MODEL_INVALID_OUTPUT
    assert [call["round"] for call in gateway.calls] == [0, 0, 1, 1]


def test_neighbour_only_retrieve_reads_neighbours(store, settings):
    """只给已知邻居 ID 的合法 retrieve 不应失败，也不应消耗额度后报错。"""

    neighbour_only = f'{{"action": "retrieve", "queries": [], "neighbor_paragraph_ids": ["{PID1}"]}}'
    detail, gateway = run(store, settings, [QUERIES, neighbour_only, final_json()])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.label == "支持"
    assert detail.accounting.supplemental_rounds_used == 1
    assert detail.accounting.repair_requests_used == 0
    assert [call["round"] for call in gateway.calls] == [0, 0, 1]


def test_retrieve_without_queries_or_neighbours_is_repaired(store, settings):
    detail, gateway = run(store, settings, [QUERIES, '{"action": "retrieve"}', RETRIEVE, final_json()])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.accounting.repair_requests_used == 1
    assert gateway.calls[2]["purpose"] == "output_repair"


def test_first_empty_retrieval_rejects_a_neighbour_only_retrieve(store, settings):
    neighbour_only = f'{{"action": "retrieve", "neighbor_paragraph_ids": ["{PID1}"]}}'
    detail, gateway = run(store, settings, ['{"queries": ["zzzz"]}', neighbour_only, RETRIEVE, final_json()])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.accounting.repair_requests_used == 1
    assert gateway.calls[2]["purpose"] == "output_repair"


def test_evidence_from_a_paragraph_outside_the_context_is_repaired(store, settings):
    """引用未进入本次上下文的段落要修复，不能拿同来源的其他段落背书。"""

    detail, gateway = run(store, settings,
                          [QUERIES, final_json(quote=QUOTE2, paragraph_id=PID2), final_json()])
    assert detail.status is TaskStatus.COMPLETED
    assert detail.decision.evidence[0].paragraph_id == PID1
    assert detail.accounting.repair_requests_used == 1
    assert gateway.calls[2]["purpose"] == "output_repair"


def test_quote_error_after_the_single_repair_is_used_reports_quote_mismatch(store, settings):
    """摘录修复额度已用尽时报 QUOTE_MISMATCH，而不是 MODEL_INVALID_OUTPUT。"""

    detail, gateway = run(store, settings,
                          [QUERIES, '{"action": "retrieve"}', RETRIEVE, final_json(quote="wrong")])
    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.QUOTE_MISMATCH
    # The structural repair consumed the single global repair slot.
    assert detail.accounting.repair_requests_used == 1
    assert gateway.calls[2]["purpose"] == "output_repair"


# ------------------------------------------------ decision output contract (#62)


def test_decision_prompt_declares_the_array_fields_and_a_minimal_shape(store, settings):
    """三个字段是字符串数组这件事必须由提示词说清楚（Issue #62）。

    真实模型对单值自然写成字符串（`"scope_differences":"…"`），而 `DecisionDraft`
    要求 `list[str]`，于是一份语义上已判对的输出被整单丢弃。提示词不给类型、只靠
    修复兜底，就等于把唯一一次修复额度花在信息不足的提示上。
    """

    _, gateway = run(store, settings, [QUERIES, final_json()])
    prompt = next(call["prompt"] for call in gateway.calls if call["purpose"] == "decision")

    assert "字符串数组" in prompt
    example, _ = json.JSONDecoder().raw_decode(prompt[prompt.index("{", prompt.index("最小形状")):])
    decision = example["decision"]
    # 示例里三个字段都是数组字面量：没有内容写 []，而不是省略该字段或写空串。
    for field in ("supported_parts", "scope_differences", "limitations"):
        assert isinstance(decision[field], list), field
    assert isinstance(decision["evidence"], list)
    assert isinstance(decision["evidence"][0], dict)


def test_repair_note_names_every_decision_field_that_broke_the_contract(store, settings):
    """修复提示词要指出 decision 里哪个字段不合契约，不能只说「动作字段不合法」。"""

    broken = final_json(scope_differences="论断范围更窄", limitations="仅单一结果句")
    detail, gateway = run(store, settings, [QUERIES, broken, final_json()])

    assert detail.status is TaskStatus.COMPLETED
    assert detail.accounting.repair_requests_used == 1
    repair = next(call["prompt"] for call in gateway.calls if call["purpose"] == "output_repair")
    # 一次修复的输入要带本次响应里全部可检测错误（测试方案「任务内澄清、隔离与多步执行」）。
    assert "final.decision.scope_differences" in repair
    assert "final.decision.limitations" in repair
    assert "list_type" in repair
    # 旧实现把这句当成全部诊断，方向指到了 action 上。
    assert "动作字段不合法" not in repair


def test_repair_note_locates_a_malformed_retrieve_payload(store, settings):
    """retrieve 分支同样要给出字段路径：出错的是载荷，从来不是 action。"""

    detail, gateway = run(store, settings,
                          ['{"queries": ["zzzz"]}', '{"action": "retrieve", "queries": "mortality"}',
                           RETRIEVE, final_json()])

    assert detail.status is TaskStatus.COMPLETED
    repair = next(call["prompt"] for call in gateway.calls if call["purpose"] == "output_repair")
    assert "retrieve.queries" in repair
    assert "动作字段不合法" not in repair


# -------------------------------- top-level strictness of the output contract (#79)


def _with_stray_top_level_field(text: str, **stray) -> str:
    """A legal response plus fields the contract does not declare, at the top level."""

    return json.dumps({**json.loads(text), **stray}, ensure_ascii=False)


def test_a_field_outside_the_contract_is_rejected_at_the_top_level_in_both_branches():
    """同一类输入（契约外顶层字段）在两个分支必须给出同一结论（Issue #79）。

    旧实现里 `final` 只把 `decision` 送进校验，多余键在校验**之前**就被丢掉，
    `extra="forbid"` 根本没机会看到它们：`retrieve` 报 `extra_forbidden`，`final`
    静默通过。严格度是契约的属性，不能取决于解析函数挑了哪些键。
    """

    stray_final = _with_stray_top_level_field(final_json(), confidence=0.9)
    stray_retrieve = _with_stray_top_level_field(RETRIEVE, confidence=0.9)

    for payload, branch in ((stray_final, "final"), (stray_retrieve, "retrieve")):
        with pytest.raises(OutputError) as raised:
            parse_decision_output(payload)
        # 诊断给出「被校验的分支 + 字段路径」，与 #62 的字段定位口径一致。
        assert f"{branch}.confidence: extra_forbidden" in str(raised.value), branch


def test_a_stray_top_level_field_in_a_final_response_costs_one_repair_not_the_task(store, settings):
    """final 带契约外顶层字段：拒收但可修，修好后照常完成，不得静默通过也不得直接失败。

    收紧 `final` 是线上行为变化，所以把它钉在「消耗一次修复」而不是「任务失败」上：
    诊断指名了要删的键，模型有一次机会改对（Issue #79 影响 2）。
    """

    stray = _with_stray_top_level_field(final_json(), confidence=0.9)
    detail, gateway = run(store, settings, [QUERIES, stray, final_json()])

    assert detail.status is TaskStatus.COMPLETED
    assert detail.label == "支持"
    assert detail.accounting.repair_requests_used == 1
    # 静默通过的话这里只会有两次调用，也没有 output_repair。
    assert [call["purpose"] for call in gateway.calls] == ["query_generation", "decision", "output_repair"]
    repair = gateway.calls[2]["prompt"]
    assert "final.confidence" in repair
    assert "extra_forbidden" in repair


def test_a_stray_top_level_field_that_survives_the_repair_is_model_invalid_output(store, settings):
    """修复后仍带契约外字段则终态 MODEL_INVALID_OUTPUT，且不暗增修复额度。"""

    stray = _with_stray_top_level_field(final_json(), confidence=0.9)
    detail, _ = run(store, settings, [QUERIES, stray, stray])

    assert detail.status is TaskStatus.FAILED
    assert detail.error_code is ErrorCode.MODEL_INVALID_OUTPUT
    assert detail.label is None and detail.decision is None
    assert detail.accounting.repair_requests_used == 1


# ---------------------------- candidate ids copied verbatim (#74)


def test_decision_prompt_requires_the_candidate_id_to_be_copied_verbatim(store, settings):
    """候选 ID 的 `p:` 前缀必须由提示词点名（Issue #74）。

    候选片段按 `[<段落 ID>]（section）原文` 渲染，而 ID 自己带 `p:` 前缀
    （`domain/text.py:paragraph_id`）。提示词原先只说 `evidence` 每项含 `paragraph_id`，
    模型忠实照抄却漏掉 `p:`，逐字定位必然失败。本用例钉住两件事：最小形状的占位说明
    指向候选片段方括号内的 ID，规则句同时说出「原样照抄」「方括号」与 `p:`。
    """

    _, gateway = run(store, settings, [QUERIES, final_json()])
    prompt = next(call["prompt"] for call in gateway.calls if call["purpose"] == "decision")

    # 规则的两端：渲染出来的形状，以及 ID 自己带的前缀。
    assert f"[{PID1}]（" in prompt

    example, _ = json.JSONDecoder().raw_decode(prompt[prompt.index("{", prompt.index("最小形状")):])
    placeholder = example["decision"]["evidence"][0]["paragraph_id"]
    assert "原样照抄" in placeholder and "方括号" in placeholder

    rule = prompt[prompt.index("paragraph_id 必须"):][:120]
    assert "原样照抄" in rule and "方括号" in rule and "p:" in rule


def test_an_id_that_lost_the_p_prefix_is_repaired_with_the_candidate_id(store, settings):
    """ID 漏掉 `p:` 时，修复输入要给出候选片段里的那个 ID（Issue #74）。

    标签与引文都对，唯一的问题是 ID 少了两个字符。旧措辞只说「段落未进入本次判断的
    上下文」——而那次上下文里明明有这个段落，模型无从知道该抄的是哪一个串。校验本身
    不放宽：ID 仍须与候选完全一致，这里只改这一次修复的输入。
    """

    detail, gateway = run(store, settings, [QUERIES, final_json(paragraph_id=PID1[2:]), final_json()])

    assert detail.status is TaskStatus.COMPLETED
    assert detail.decision.evidence[0].paragraph_id == PID1
    assert detail.accounting.repair_requests_used == 1
    repair = next(call["prompt"] for call in gateway.calls if call["purpose"] == "output_repair")
    assert "漏掉了开头的 p: 前缀" in repair
    assert "未进入本次判断的上下文" not in repair


def test_a_bracketed_id_is_repaired_with_the_unwrapped_candidate_id(store, settings):
    """把候选片段的方括号一起照抄的那一类，同样要给出候选里的 ID。

    `#62` 的记录里出现过一例（提示词展示 `[<id>]`，模型连方括号一起写进
    `paragraph_id`）。它与漏前缀是同一类「忠实复制失败」，修复说明要给可用的那个串。
    """

    detail, gateway = run(store, settings, [QUERIES, final_json(paragraph_id=f"[{PID1}]"), final_json()])

    assert detail.status is TaskStatus.COMPLETED
    assert detail.decision.evidence[0].paragraph_id == PID1
    assert detail.accounting.repair_requests_used == 1
    repair = next(call["prompt"] for call in gateway.calls if call["purpose"] == "output_repair")
    assert "把候选片段里的方括号一起写了进去" in repair


# ------------------------------------------- cancel-vs-completion race (round 3)


def test_cancel_accepted_during_the_final_model_call_wins(store, settings):
    """最终模型调用期间受理的取消必须赢过完成结果（复审复现路径）。

    走真实认领路径进入 RUNNING，取消在最终 decision 响应返回时落库；此前的实现会把
    任务落成 COMPLETED 并带确定判断。
    """

    gateway = CancellingGateway([QUERIES, final_json()], store, "t1")
    workflow = BoundedWorkflow(
        store=store, resolver=FakeResolver(), fulltext=FakeFulltext(),
        retriever=StoreRetriever(store, settings.retrieval_context_limit),
        prompts=PaperPromptBuilder(), gateway=gateway, settings=settings,
    )
    task = make_task(store, settings)
    store.claim_next(time.time() + 180)  # QUEUED -> RUNNING via the real claim path
    assert store.cancel_accepted("t1") is False

    detail = asyncio.run(workflow.run(task, time.monotonic() + 180))

    assert store.cancel_accepted("t1") is True
    assert detail.status is TaskStatus.CANCELLED
    assert detail.label is None and detail.decision is None
    assert detail.error_code is None


def test_cancel_accepted_before_a_failure_still_wins(store, settings):
    """取消先于失败受理时，终态是 CANCELLED，而不是 FAILED。"""

    gateway = CancellingGateway([QUERIES, ContractError(ErrorCode.UPSTREAM_TIMEOUT, "timeout")], store, "t1",
                                when="before")
    workflow = BoundedWorkflow(
        store=store, resolver=FakeResolver(), fulltext=FakeFulltext(),
        retriever=StoreRetriever(store, settings.retrieval_context_limit),
        prompts=PaperPromptBuilder(), gateway=gateway, settings=settings,
    )
    task = make_task(store, settings)
    store.claim_next(time.time() + 180)

    detail = asyncio.run(workflow.run(task, time.monotonic() + 180))

    assert detail.status is TaskStatus.CANCELLED
    assert detail.label is None and detail.decision is None


def _snapshot(settings):
    """``make_task`` hardcodes id ``t1``; the second task needs its own run config."""

    return RunConfigSnapshot(profile="daily", config_digest="d", snapshot_ref="r",
                             authorized_recipients=["Agnes"], limits=settings.limits,
                             timeouts=settings.timeouts, observability=settings.observability)


def test_a_linked_task_never_sees_the_previous_claim(store, settings):
    """上一条论断不得进入下一条任务（测试方案「任务内澄清」:83）。

    ``previous_id`` 只是记录关联：第二个任务的提示词里只能出现它自己的论断，原任务
    的原句与判断都不得进入上下文；原任务记录也不能被新任务覆盖。
    """

    old_claim = "甲论断：治疗把死亡率降低了 20%，老年亚组同样有效。"
    new_claim = "乙论断：治疗缩短了住院时间。"

    def run_one(task, responses):
        gateway = FakeGateway(responses)
        workflow = BoundedWorkflow(
            store=store, resolver=FakeResolver(), fulltext=FakeFulltext(),
            retriever=StoreRetriever(store, settings.retrieval_context_limit),
            prompts=PaperPromptBuilder(), gateway=gateway, settings=settings,
        )
        store.create(task, _snapshot(settings), criteria_reference("rev"))
        return asyncio.run(workflow.run(task, time.monotonic() + 180)), gateway

    old_task = TaskInput(id="t1", claim=old_claim, doi="10.1000/xyz", config_digest="d",
                         authorized_recipients=("Agnes",))
    run_one(old_task, [QUERIES, final_json()])

    new_task = TaskInput(id="t2", claim=new_claim, doi="10.1000/xyz", config_digest="d",
                         authorized_recipients=("Agnes",), previous_id="t1")
    detail, gateway = run_one(new_task, [QUERIES, final_json()])

    prompts = "\n".join(call["prompt"] for call in gateway.calls)
    assert new_claim in prompts
    assert old_claim not in prompts
    # 逐段核对，避免只靠整句 miss 就宣布没问题。
    assert "老年亚组" not in prompts
    assert "死亡率降低了 20%" not in prompts

    assert detail.previous_id == "t1"
    assert detail.claim == new_claim
    # 原任务的输入不被覆盖，两条历史各自可见。
    assert store.get("t1").claim == old_claim
    assert {row.id for row in store.list()} == {"t1", "t2"}

#: 中文论断配英文正文：真实来源几乎全是英文，而考卷里的论断是中文写的。
CHINESE_CLAIM = "该治疗使死亡率下降了 20%。"


def test_a_chinese_claim_is_judged_against_an_english_body(store, settings):
    """中文论断→英文正文受支持（测试方案 `test-plan.md:69`、`:72`）。

    跨语言的桥在模型这边：正文是英文，模型把论断译成英文查询词再提交，应用自己
    不对论断语言做判定（判据只要求**英文论断→中文正文**被拒，那条由
    `sources/pmc.py` 的 `require_english` 负责）。

    所以要钉的是两件事：中文论断不被系统性阻断，且模型给的英文查询确实能命中英文
    正文，并让引用通过逐字定位。
    """

    detail, _ = run(store, settings, [RETRIEVE, final_json()], claim=CHINESE_CLAIM)

    assert detail.status is TaskStatus.COMPLETED, detail.error_code
    assert detail.error_code is None
    assert detail.label is not None and detail.label.value == "支持"
    assert [item.paragraph_id for item in detail.decision.evidence] == [PID1]


def test_a_chinese_query_against_an_english_body_finds_nothing(store, settings):
    """对照：同一个中文论断，若直接用中文查询词检索英文正文，命中为空。

    这条钉住的是**机制**而不是缺陷：unicode61 把连续中文当一个词元，英文正文里
    不存在这个词元，所以中文查询必然落空。工作流随后按有界检索自返回「证据不足」
    （`graph/workflow.py` 的 `_insufficient()`），这不是模型的判断，标签来源要
    记成工作流降级。

    有了这条对照，上面那条才不是「怎么都能过」——把桥抽掉，结论立刻从「支持」
    变成「证据不足」。
    """

    chinese_retrieve = '{"action": "retrieve", "queries": ["死亡率"], "neighbor_paragraph_ids": []}'
    detail, gateway = run(store, settings, [chinese_retrieve, chinese_retrieve], claim=CHINESE_CLAIM)

    assert detail.status is TaskStatus.COMPLETED, detail.error_code
    assert detail.error_code is ErrorCode.RETRIEVAL_EMPTY
    assert detail.label is not None and detail.label.value == "证据不足"
    assert detail.decision is not None and detail.decision.evidence == []
    # 模型只被问过两次（两轮查询），没有拿到第三轮去「猜」一个判断。
    assert len(gateway.calls) == 2

