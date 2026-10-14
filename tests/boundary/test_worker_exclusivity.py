"""多 worker 下的独占与遗留结算（Issue #34）。

「同一时刻只执行一个任务」以前只靠运行约定（只起一个 worker）保证。这组用例判定
它已成为**存储层不变量**：一行处于 ``RUNNING`` 时 ``claim_next`` 拒绝领取；遗留
``RUNNING`` 只在「可证已死」时才被结算，因此第二个 worker 的启动不会再杀掉第一个
worker 正在跑的任务。

两个 ``SqliteStore`` 开在同一份库上即等价于两个进程：各自一条连接，只共享文件。
并发那一条用线程 + 栅栏让两个连接同时进 ``BEGIN IMMEDIATE``。
"""

import asyncio
import threading
import time
from dataclasses import replace

import pytest

from paper_evidence.config import Settings
from paper_evidence.domain import TaskStatus
from paper_evidence.domain.contracts import RunConfigSnapshot
from paper_evidence.domain.records import TaskInput
from paper_evidence.domain.rules import criteria_reference
from paper_evidence.storage import sqlite
from paper_evidence.storage.sqlite import SqliteStore
from paper_evidence.worker.runner import SingleTaskWorker


@pytest.fixture
def settings(tmp_path):
    return replace(Settings.from_env(), data_dir=tmp_path, contact_email="")


@pytest.fixture
def store(tmp_path):
    db = SqliteStore(tmp_path / "exclusivity.sqlite3")
    yield db
    db.close()


def make_task(store, task_id="t1", doi="10.1000/xyz"):
    """Queue one task the way the API does."""

    settings = replace(Settings.from_env(), contact_email="")
    task = TaskInput(id=task_id, claim="The treatment reduced mortality.", doi=doi,
                     config_digest="d", authorized_recipients=("Agnes",))
    run_config = RunConfigSnapshot(profile="daily", config_digest="d", snapshot_ref="r",
                                   authorized_recipients=["Agnes"], limits=settings.limits,
                                   timeouts=settings.timeouts, observability=settings.observability)
    store.create(task, run_config, criteria_reference("rev"))
    return task


class _InstantWorkflow:
    """Stand-in that settles its own task at once: the claim path is what is under test."""

    def __init__(self, store) -> None:
        self._store = store

    async def run(self, task, deadline):
        self._store.finish(task.id, status=TaskStatus.COMPLETED, stage="evidence_validation",
                           error_code=None, label="支持", decision=None)
        return self._store.get(task.id)


# ------------------------------------------------------------------- 独占不变量


def test_a_running_task_blocks_another_claim(store, tmp_path):
    """另一个进程领不到任务：队列非空，但已有在途任务时领取返回 None。"""

    make_task(store, "t1")
    make_task(store, "t2")
    other = SqliteStore(tmp_path / "exclusivity.sqlite3")
    try:
        assert store.claim_next(time.time() + 180) is not None
        assert other.claim_next(time.time() + 180) is None
        assert store.get("t1").status is TaskStatus.RUNNING
        assert store.get("t2").status is TaskStatus.QUEUED
    finally:
        other.close()


def test_concurrent_claims_produce_exactly_one_winner(tmp_path):
    """两个连接同时领取：只有一个拿到任务，第二个任务留在队列里。

    两个 worker 各领一条并行执行是 #34 要消除的行为，所以这里让两个连接用栅栏
    一起进 ``BEGIN IMMEDIATE``，断言「恰有一个赢家」而不是「谁先谁后」。
    """

    path = tmp_path / "exclusivity.sqlite3"
    first = SqliteStore(path)
    second = SqliteStore(path)
    make_task(first, "t1")
    make_task(first, "t2")

    barrier = threading.Barrier(2)
    results: list[object] = [None, None]

    def claim(index, handle):
        barrier.wait(timeout=10)
        results[index] = handle.claim_next(time.time() + 180)

    threads = [threading.Thread(target=claim, args=(index, handle)) for index, handle in enumerate((first, second))]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        assert not any(thread.is_alive() for thread in threads)

        claimed = [task for task in results if task is not None]
        assert len(claimed) == 1, f"应当恰有一个 worker 领到任务，实际 {results!r}"
        assert claimed[0].id == "t1"
        assert {row.id: row.status for row in first.list()} == {
            "t1": TaskStatus.RUNNING,
            "t2": TaskStatus.QUEUED,
        }
    finally:
        first.close()
        second.close()


# ------------------------------------------------------------- 遗留行的判定依据


def test_a_second_worker_startup_keeps_a_live_task_running(store, tmp_path):
    """第二个 worker 启动不得把在途任务翻成 INTERRUPTED（本轮修掉的危险行为）。

    以前启动结算无条件处理所有 ``RUNNING``：第二个 worker 一起来，第一个 worker
    正在跑的任务就被翻成 ``INTERRUPTED``，而后 ``finish`` 的条件写入拒绝真实终态，
    任务不可恢复。现在结算只看「可证已死」的行。
    """

    make_task(store, "t1")
    assert store.claim_next(time.time() + 180) is not None

    other = SqliteStore(tmp_path / "exclusivity.sqlite3")
    try:
        assert other.settle_orphaned_running() == 0
        assert store.get("t1").status is TaskStatus.RUNNING
        # 在途任务仍能写出自己的真实终态
        assert store.finish("t1", status=TaskStatus.COMPLETED, stage="evidence_validation",
                            error_code=None, label="支持", decision=None) is True
        assert store.get("t1").status is TaskStatus.COMPLETED
    finally:
        other.close()


def test_a_leftover_running_row_past_its_deadline_settles_as_interrupted(store):
    """崩溃留下的行过了自己的 deadline 才结算，且仍按 INTERRUPTED 收尾。"""

    make_task(store, "t1")
    store.claim_next(time.time() - 1)  # RUNNING, deadline 已过

    assert store.settle_orphaned_running() == 1
    settled = store.get("t1")
    assert settled.status is TaskStatus.INTERRUPTED
    assert settled.finished_at is not None


def test_a_leftover_running_row_without_a_deadline_settles_as_interrupted(store):
    """没有 deadline 的 RUNNING 行也是孤儿：领取路径一定写入 deadline。

    不能把它当成「可能还活着」放着不管——``claim_next`` 现在看到任何 ``RUNNING``
    都拒绝领取，留着它等于队列永久卡住。
    """

    make_task(store, "t1")
    store.claim_next()  # deadline 缺省为 None

    assert store.settle_orphaned_running() == 1
    assert store.get("t1").status is TaskStatus.INTERRUPTED


def test_a_cancel_accepted_leftover_settles_as_cancelled(store, monkeypatch):
    """受理过取消的遗留行按 CANCELLED 收尾：结算不把它改写成其他终态。"""

    make_task(store, "t1")
    store.claim_next(time.time() + 180)
    assert store.request_cancel("t1").status is TaskStatus.RUNNING
    assert store.cancel_accepted("t1") is True

    # 时间越过 deadline：只有这时这行才是「可证已死」的遗留行
    monkeypatch.setattr(sqlite, "_epoch", lambda: time.time() + 3600)
    assert store.settle_orphaned_running() == 1
    assert store.get("t1").status is TaskStatus.CANCELLED


def test_settling_a_leftover_does_not_claim_it_back(store):
    """结算过的任务不会被重新领取：它已是终态，不是 QUEUED。"""

    make_task(store, "t1")
    store.claim_next(time.time() - 1)
    assert store.settle_orphaned_running() == 1

    assert store.claim_next(time.time() + 180) is None
    assert store.get("t1").status is TaskStatus.INTERRUPTED


# ------------------------------------------------------------------ 队列恢复


def test_the_queue_resumes_after_a_crash_leftover_is_settled(store, settings):
    """结算之后队列不永久卡住：worker 下一轮就能领到后面的 QUEUED 任务。

    恢复必须发生在领取之前：遗留行在进程重启那一刻往往还没到 deadline，只靠启动
    结算挡不住它，所以 ``run_once`` 每轮先结算再领取（Issue #34 验收表第 3、5 条）。
    """

    make_task(store, "t1")
    store.claim_next(time.time() - 1)  # t1 -> RUNNING，deadline 已过（模拟崩溃遗留行）
    make_task(store, "t2")

    # 遗留行仍然挡着：这一步只证明守卫在起作用，不改变状态
    assert store.claim_next(time.time() + 180) is None

    worker = SingleTaskWorker(store, lambda task: _InstantWorkflow(store), settings)
    assert asyncio.run(worker.run_once()) is True

    assert {row.id: row.status for row in store.list()} == {
        "t1": TaskStatus.INTERRUPTED,
        "t2": TaskStatus.COMPLETED,
    }
