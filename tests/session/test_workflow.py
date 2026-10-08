"""Bounded multi-step workflow: budgets, repair, cancellation and terminals."""

import asyncio
import time
from dataclasses import replace

import pytest

from paper_evidence.agents.prompts import PaperPromptBuilder
from paper_evidence.config import Settings
from paper_evidence.domain import ContractError, ErrorCode, TaskStatus
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


def final_json(quote=QUOTE1, label="支持", paragraph_id=PID1, evidence=None):
    import json

    items = [{"paragraph_id": paragraph_id, "quote": quote}] if evidence is None else evidence
    return json.dumps({
        "action": "final",
        "decision": {
            "label": label, "rationale": "r", "supported_parts": [], "scope_differences": [],
            "limitations": [], "evidence": items,
        },
    }, ensure_ascii=False)


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
    def __init__(self, error=None):
        self.error = error

    async def fetch(self, doi, deadline):
        if self.error:
            raise self.error
        record = SourceRecord(title="Demo", doi=doi, pmcid="PMC123", license="CC BY", version="1",
                              access_url="https://example.org/a", retrieved_at="2026-10-01T00:00:00+00:00",
                              version_hash=VERSION_HASH)
        return SourceSnapshot(source_id=f"PMC123:{VERSION_HASH}", metadata=record, jats_bytes=JATS)


class FakeGateway:
    """Returns canned responses in order and records the logical requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, request_id, prompt, deadline, *, purpose, round_index, prompt_version="",
                       context_paragraph_ids=None, repairs_request_id=None):
        self.calls.append({"request_id": request_id, "purpose": purpose, "round": round_index})
        item = self.responses.pop(0)
        failed = isinstance(item, Exception)
        attempt = ModelAttempt(
            attempt_id=f"{request_id}:1", attempt_index=1, span_id="s", gateway_request_id=None,
            upstream_response_id=None, configured_model="m", deployment_id="d", recipient="Agnes",
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
        deadline=None, limits=None):
    if limits is not None:
        settings = replace(settings, limits=limits)
    gateway = FakeGateway(responses)
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
