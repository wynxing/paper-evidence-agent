"""单进程、一次一个任务（测试方案「性能」第一条判定）。

判定原文：「保持单进程、一次一个任务……再提交任务时，后来的任务停留在
``QUEUED``，不另起执行器。」

这里的「不另起执行器」按可观察的行为断言：一条任务在途时，新提交的任务仍是
``QUEUED``，且工作流实例数不增加。实现上它来自 ``drain``/``drain_forever``
的顺序循环——``run_once`` 返回之前不会再领取下一条。
"""

import asyncio

from fixtures import settings, store  # noqa: F401  (pytest fixtures)
from harness import WorkflowHarness, enqueue
from paper_evidence.domain import TaskStatus
from paper_evidence.worker.runner import SingleTaskWorker, drain, drain_forever


def test_one_run_once_claims_at_most_one_task(store, settings):
    """每条 ``run_once`` 只领取一条任务，其余保持在队列里。"""

    for task_id in ("t1", "t2", "t3"):
        enqueue(store, settings, task_id)

    harness = WorkflowHarness(store)
    worker = SingleTaskWorker(store, harness, settings)

    assert asyncio.run(worker.run_once()) is True
    assert harness.claims == ["t1"]
    assert {row.id: row.status for row in store.list()} == {
        "t1": TaskStatus.COMPLETED,
        "t2": TaskStatus.QUEUED,
        "t3": TaskStatus.QUEUED,
    }

    assert asyncio.run(worker.run_once()) is True
    assert harness.claims == ["t1", "t2"]
    assert store.get("t3").status is TaskStatus.QUEUED


def test_the_drain_loop_runs_tasks_one_after_another(store, settings):
    """``drain`` 顺序处理队列，并发峰值恒为 1。"""

    for task_id in ("t1", "t2", "t3"):
        enqueue(store, settings, task_id)

    harness = WorkflowHarness(store)
    worker = SingleTaskWorker(store, harness, settings)

    assert asyncio.run(drain(worker)) == 3
    assert harness.claims == ["t1", "t2", "t3"]
    assert harness.max_in_flight == 1


def test_an_empty_queue_makes_run_once_report_nothing(store, settings):
    """队列空时 ``run_once`` 返回 ``False``，让 loop 去等待而不是空转领取。"""

    harness = WorkflowHarness(store)
    worker = SingleTaskWorker(store, harness, settings)
    assert asyncio.run(worker.run_once()) is False
    assert harness.workflows == []


def test_a_task_submitted_while_another_runs_stays_queued(store, settings):
    """在途任务未结束时，新提交的任务停在 QUEUED，没有第二个执行器接手。"""

    enqueue(store, settings, "t1")

    async def scenario():
        gate = asyncio.Event()
        harness = WorkflowHarness(store, gate=gate)
        worker = SingleTaskWorker(store, harness, settings)

        running = asyncio.create_task(drain_forever(worker, 0.01))
        try:
            await asyncio.wait_for(harness.first_claim.wait(), 10)

            # 逐项判定的那一刻：t1 还在途，用户又提交了一条
            enqueue(store, settings, "t2")
            # 常驻循环此刻正 await 在 t1 上；给它充分的机会去（错误地）领取 t2
            await asyncio.sleep(0.2)

            assert store.get("t2").status is TaskStatus.QUEUED
            assert harness.claims == ["t1"]
            assert len(harness.workflows) == 1
            assert harness.max_in_flight == 1

            gate.set()
            await asyncio.wait_for(harness.second_claim.wait(), 10)
            assert store.get("t1").status is TaskStatus.COMPLETED

            # 同一条常驻循环接着处理第二条：仍然是一条接一条，不是两条并行
            await _until(lambda: store.get("t2").status is TaskStatus.COMPLETED)
            assert harness.claims == ["t1", "t2"]
            assert harness.max_in_flight == 1
        finally:
            running.cancel()
            try:
                await running
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())

    assert {row.id: row.status for row in store.list()} == {
        "t1": TaskStatus.COMPLETED,
        "t2": TaskStatus.COMPLETED,
    }


async def _until(predicate, *, attempts: int = 300, interval: float = 0.01) -> None:
    """Poll a predicate on the event loop instead of assuming a scheduling order."""

    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("等待条件在超时前未成立")
