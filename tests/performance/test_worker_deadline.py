"""总执行时限与三档超时边界（测试方案「性能」受控验收）。

受控验收要求 45 秒模型尝试、15 秒来源请求、180 秒总执行时限，并「用虚拟时钟
检查超时边界」。真实等待这三档不可行，所以时间由 ``clock`` fixture 推进，
断言的是「剩余时间截短单次超时」「Retry-After 超过剩余时间不再重试」这两条
算术，而不是本机耗时。

模型侧的 Retry-After 规则走 SDK 传输，已在 `tests/tools/test_sdk_gateway.py`
覆盖（那里用的是真实时钟），本文件不重复；这里补来源侧（15 秒）同一规则，
以及真实时钟测不出的确切边界。
"""

import asyncio

import httpx
import pytest

from fixtures import clock, settings, store  # noqa: F401  (pytest fixtures)
from harness import WorkflowHarness, enqueue
from paper_evidence.domain import ContractError, ErrorCode, TaskStatus
from paper_evidence.models.recording import AttemptRecorder
from paper_evidence.sources.http import Fetcher
from paper_evidence.worker.runner import SingleTaskWorker

SOURCE_URL = "https://sources.test/works/10.1000/perf"


def _recorder(attempt_seconds: float) -> AttemptRecorder:
    return AttemptRecorder(model_alias="paper-default", configured_model="agnes-2.5-flash",
                           deployment_id="agnes-primary", recipient="Agnes",
                           attempt_seconds=attempt_seconds)


class _CapturingTransport(httpx.AsyncBaseTransport):
    """Records the per-request timeout httpx would actually apply."""

    def __init__(self, handler) -> None:
        self._handler = handler
        self.timeouts: list[float] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        timeout = request.extensions.get("timeout") or {}
        self.timeouts.append(timeout.get("read"))
        return self._handler(request)


def _fetcher(handler, *, request_seconds: float = 15) -> tuple[Fetcher, _CapturingTransport]:
    transport = _CapturingTransport(handler)
    return Fetcher(httpx.AsyncClient(transport=transport), request_seconds, "test-agent"), transport


# ------------------------------------------------------------- 任务的时钟起点


def test_the_task_clock_starts_at_claim_not_at_enqueue(store, settings, clock, monkeypatch):
    """队列等待不计入 180 秒：领取时重新起算。

    判定原文：「总时限从 RUNNING 开始，含解析/重试等待、不含队列」。
    """

    assert settings.timeouts.task_seconds == 180
    enqueue(store, settings, "t1")
    queued_at = clock.monotonic()

    clock.advance(600)  # 任务在队列里等了 10 分钟

    captured: dict[str, float | None] = {}
    original = store.claim_next

    def spy(deadline_at=None):
        captured["deadline_at"] = deadline_at
        return original(deadline_at)

    monkeypatch.setattr(store, "claim_next", spy)

    harness = WorkflowHarness(store)
    assert asyncio.run(SingleTaskWorker(store, harness, settings).run_once()) is True

    claimed_at = clock.monotonic()
    assert claimed_at - queued_at == 600
    # 领取时刻重新起算：整段 180 秒仍在，队列等待一秒都没吃掉
    assert harness.deadlines == [claimed_at + 180]
    # 落库的到期时刻是同一时刻的挂钟口径，供 API 的过期检查使用
    assert captured["deadline_at"] == clock.time() + 180
    assert store.get("t1").status is TaskStatus.COMPLETED


# ------------------------------------------------------------------ 模型尝试


def test_a_single_model_attempt_is_capped_at_45_seconds(clock):
    assert _recorder(45).timeout_for(clock.monotonic() + 300) == 45


def test_the_remaining_task_time_truncates_a_single_model_attempt(clock):
    """总时限只剩 12 秒时，单次模型尝试也从 45 秒缩到 12 秒。"""

    assert _recorder(45).timeout_for(clock.monotonic() + 12) == 12


def test_an_exhausted_task_clock_is_task_timeout_not_an_attempt(clock):
    """时钟走完时直接落 TASK_TIMEOUT，不再发一次上游请求。"""

    with pytest.raises(ContractError) as raised:
        _recorder(45).timeout_for(clock.monotonic())
    assert raised.value.error_code is ErrorCode.TASK_TIMEOUT


# ------------------------------------------------------------------ 来源请求


def test_a_source_request_is_capped_at_15_seconds(clock):
    fetcher, transport = _fetcher(lambda request: httpx.Response(200, json={}))
    asyncio.run(fetcher.get(SOURCE_URL, deadline=clock.monotonic() + 300))
    assert transport.timeouts == [15]


def test_the_remaining_task_time_truncates_a_source_request(clock):
    fetcher, transport = _fetcher(lambda request: httpx.Response(200, json={}))
    asyncio.run(fetcher.get(SOURCE_URL, deadline=clock.monotonic() + 4))
    assert transport.timeouts == [4]


def test_an_exhausted_task_clock_stops_a_source_request(clock):
    """剩余时间已耗尽：来源请求按上游超时收口，不发出去。"""

    fetcher, transport = _fetcher(lambda request: httpx.Response(200, json={}))
    with pytest.raises(ContractError) as raised:
        asyncio.run(fetcher.get(SOURCE_URL, deadline=clock.monotonic()))
    assert raised.value.error_code is ErrorCode.UPSTREAM_TIMEOUT
    assert transport.timeouts == []


def test_a_source_retry_after_beyond_the_remaining_time_is_not_waited_out(clock):
    """Retry-After 大于剩余任务时间：不发第二次请求，也不真的等下去。

    判定原文：「Retry-After 大于剩余时间不再发起重试」。
    """

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "300"})

    fetcher, _ = _fetcher(handler)
    with pytest.raises(ContractError) as raised:
        asyncio.run(fetcher.get(SOURCE_URL, deadline=clock.monotonic() + 20))
    assert raised.value.error_code is ErrorCode.UPSTREAM_TIMEOUT
    assert len(calls) == 1


def test_a_retry_after_within_the_remaining_time_is_waited_out_then_retried(clock):
    """反面：Retry-After 没超过剩余时间时照常退避并重试一次。"""

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            # 0.05 秒而不是 5 秒：这里要判定的是「没超过剩余时间就照常退避」，
            # 不是退避多久，真实等待只会拖慢套件。
            return httpx.Response(429, headers={"Retry-After": "0.05"})
        return httpx.Response(200, json={"ok": True})

    fetcher, _ = _fetcher(handler)
    response = asyncio.run(fetcher.get(SOURCE_URL, deadline=clock.monotonic() + 60))
    assert response.status_code == 200
    assert len(calls) == 2


def test_a_backoff_wait_is_interruptible(clock):
    """退避等待必须可被取消中断，不能被吞掉后继续重试（测试方案「取消中断退避」）。"""

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "5"})

    fetcher, _ = _fetcher(handler)

    async def scenario():
        pending = asyncio.create_task(fetcher.get(SOURCE_URL, deadline=clock.monotonic() + 60))
        for _ in range(400):
            if calls:
                break
            await asyncio.sleep(0.005)
        assert calls, "第一个请求未发出，退避分支没走到"
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending

    asyncio.run(scenario())
    assert len(calls) == 1
