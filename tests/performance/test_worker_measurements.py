"""单任务测量记录：延迟、逻辑请求数、上游尝试数、token（测试方案「性能」）。

被测的是 `tests/performance/measure.py` 的读数口径，喂给它的是真实 ``SqliteStore``
的行。刻意钉住两处容易写错的判定：

* 缺失的 token 是**未知**而不是 0；
* 逻辑请求数与上游尝试数不是同一个数（一次逻辑请求可以派发多次尝试）。

这里不产出性能结论：只有一次本机运行，且上游是构造记录，不是真实模型。
"""

import asyncio

from fixtures import settings, store  # noqa: F401  (pytest fixtures)
from harness import WorkflowHarness, enqueue
from measure import measure, measure_run
from paper_evidence.domain.contracts import ModelAttempt, ModelCall, TokenUsage
from paper_evidence.worker.runner import SingleTaskWorker

USAGE = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)


def attempt(index: int, usage: TokenUsage | None = None) -> ModelAttempt:
    return ModelAttempt(
        attempt_id=f"r1:{index}", attempt_index=index, span_id=f"span:r1:{index}",
        gateway_request_id=None, upstream_response_id=None,
        configured_model="agnes-2.5-flash", provider_model="openai/agnes-2.5-flash",
        deployment_id="agnes-primary", recipient="Agnes",
        response_model="agnes", verified_model_version=None, recovery_kind="none",
        recovery_reason=None, status="success", error_code=None, duration_ms=1, usage=usage,
    )


def call(request_id: str, attempts: list[ModelAttempt]) -> ModelCall:
    return ModelCall(
        request_id=request_id, purpose="query_generation", round=0, model_alias="paper-default",
        prompt_version="v", params_digest="d", context_paragraph_ids=[],
        repairs_request_id=None, attempts=attempts,
    )


def recording_body(calls):
    """A stand-in workflow body that writes the given model calls, then returns."""

    async def body(task, harness):
        for item in calls:
            harness.store.record_model_call(task.id, item)

    return body


def run_worker(store, settings, calls):
    harness = WorkflowHarness(store, body=recording_body(calls))
    worker = SingleTaskWorker(store, harness, settings)
    enqueue(store, settings, "t1")
    return measure_run(store, "t1", lambda: asyncio.run(worker.run_once()))


def test_logical_requests_and_upstream_attempts_are_counted_separately(store, settings):
    """两次逻辑请求、其中一次重试过：逻辑请求数 2，上游尝试数 3。"""

    calls = [call("r1", [attempt(1), attempt(2)]), call("r2", [attempt(1)])]
    measurement, processed = run_worker(store, settings, calls)

    assert processed is True
    assert measurement.logical_requests == 2
    assert measurement.upstream_attempts == 3
    assert measurement.observed_upstream_attempts == 3
    assert measurement.status == "COMPLETED"


def test_a_missing_usage_is_unknown_not_zero(store, settings):
    """没有 ``usage`` 的尝试让 token 记为未知，不写 0。"""

    measurement, _ = run_worker(store, settings, [call("r1", [attempt(1)])])

    assert measurement.tokens.prompt is None
    assert measurement.tokens.completion is None
    assert measurement.tokens.total is None
    assert measurement.tokens.known is False
    assert measurement.tokens.attempts_reporting == 0
    assert measurement.tokens.attempts_total == 1


def test_one_unobserved_attempt_keeps_the_whole_field_unknown(store, settings):
    """一次成功、一次缺 usage：该字段未知，而不是只有一半的偏小数。"""

    measurement, _ = run_worker(store, settings, [call("r1", [attempt(1, USAGE), attempt(2, None)])])

    assert measurement.tokens.prompt is None
    assert measurement.tokens.total is None
    assert measurement.tokens.attempts_reporting == 1
    assert measurement.tokens.attempts_total == 2


def test_recorded_usage_is_summed_across_attempts(store, settings):
    measurement, _ = run_worker(store, settings, [call("r1", [attempt(1, USAGE), attempt(2, USAGE)])])

    assert measurement.tokens.known is True
    assert measurement.tokens.prompt == 20
    assert measurement.tokens.completion == 40
    assert measurement.tokens.total == 60


def test_a_call_without_a_dispatched_attempt_is_unverified(store, settings):
    """一条没派发过上游尝试的调用：账记为 unverified，尝试数是未知而非 0。"""

    measurement, _ = run_worker(store, settings, [call("r1", [])])
    detail = store.get("t1")

    assert detail.accounting.verification == "unverified"
    assert detail.accounting.upstream_attempts_used is None
    assert detail.accounting.reason == "attempt_records_missing"
    assert measurement.observed_upstream_attempts == 0
    assert measurement.tokens.total is None


def test_the_latency_of_a_claimed_run_is_recorded(store, settings):
    """延迟由测量方在本机计时；构造的上游只让这一步可重复，不做性能结论。"""

    async def slow_body(task, harness):
        await asyncio.sleep(0.02)

    harness = WorkflowHarness(store, body=slow_body)
    worker = SingleTaskWorker(store, harness, settings)
    enqueue(store, settings, "t1")

    measurement, processed = measure_run(store, "t1", lambda: asyncio.run(worker.run_once()))

    assert processed is True
    # 下界取 10ms 是因为本机事件循环会把 20ms 的 sleep 提前几毫秒叫醒；
    # 上界只是防跑飞，不是性能判定。
    assert measurement.latency_ms is not None and 10 <= measurement.latency_ms <= 2000
    assert measurement.persisted_ms is not None and measurement.persisted_ms >= 0


def test_a_queued_task_has_no_latency_and_no_timestamps(store, settings):
    """还在排队的任务没有 started_at/finished_at：延迟未知，不估一个数。"""

    enqueue(store, settings, "t1")
    measurement = measure(store, "t1")

    assert measurement.status == "QUEUED"
    assert measurement.latency_ms is None
    assert measurement.persisted_ms is None
    assert measurement.logical_requests == 0
    assert measurement.tokens.known is False
