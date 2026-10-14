"""Single-process worker: one task at a time.

The worker drains queued tasks, one per claim. The total deadline starts when the
task is atomically claimed and becomes RUNNING; it covers source processing,
model calls, retry waits and validation but not queue time.
"""

import asyncio
import logging
import time

from paper_evidence.domain import ErrorCode, TaskStatus

__all__ = ["SingleTaskWorker", "drain", "drain_forever"]

logger = logging.getLogger(__name__)


class SingleTaskWorker:
    def __init__(self, store, workflow_factory, settings) -> None:
        self._store = store
        self._workflow_factory = workflow_factory
        self._settings = settings
        self._stall: dict | None = None

    @property
    def stall(self) -> dict | None:
        """Why the last ``run_once`` claimed nothing, or ``None`` if the queue was empty.

        ``run_once`` returns ``False`` for two reasons that callers must not conflate:
        the queue is empty, or a task is already ``RUNNING`` and this worker may not
        claim past it. A one-shot ``drain`` that reports「队列已空」in the second case
        tells its operator to stop re-running while ``QUEUED`` tasks still wait (Issue
        #44 第 3.2 条). Read straight after the refused claim, so it describes that
        claim rather than the queue a moment later.
        """
        return self._stall

    async def run_once(self) -> bool:
        """Claim and process at most one task; return whether one was processed.

        领取前先结算时限已过的遗留 ``RUNNING``（见 ``settle_orphaned_running``）。
        ``claim_next`` 现在只要看到一行 ``RUNNING`` 就拒绝领取，所以一条再也跑不完的
        遗留行会把队列永久卡住；而它在启动那一刻通常还没到 deadline，只在进程启动时
        结算一次不够。每轮领取前结算，常驻模式下恢复只比 deadline 晚一个轮询间隔
        （Issue #34）。

        返回 ``False`` 时 ``stall`` 说明是不是被在途任务挡住的（``claim_next`` 还有
        第三种 ``None`` 来源——条件 ``UPDATE`` 的 ``rowcount`` 不为 1——它在
        ``BEGIN IMMEDIATE`` 之下不可达）。
        """

        await asyncio.to_thread(self._store.settle_orphaned_running)
        task_seconds = self._settings.timeouts.task_seconds
        # The run itself is bounded by a monotonic clock; the value persisted for
        # the API's expiry check is a wall-clock epoch (same clock, same duration).
        deadline = time.monotonic() + task_seconds
        task = await asyncio.to_thread(self._store.claim_next, time.time() + task_seconds)
        if task is None:
            self._stall = await asyncio.to_thread(self._store.running_task)
            return False
        self._stall = None
        try:
            # The factory is inside the guard as well: a workflow that cannot even
            # be constructed still has to settle the task it already claimed,
            # otherwise the row stays RUNNING until the next startup sweep.
            workflow = self._workflow_factory(task)
            await workflow.run(task, deadline)
        except Exception:  # unclassified execution failure keeps a null error code
            logger.exception("Workflow raised for task %s", task.id)
            await asyncio.to_thread(self._settle_failure, task.id)
        return True

    def _settle_failure(self, task_id: str) -> None:
        """Store the unclassified failure, letting an accepted cancel win.

        ``finish`` refuses a non-CANCELLED terminal on a task whose cancel was
        already accepted, so this settles that row as CANCELLED rather than
        leaving it RUNNING until the next orphan sweep.
        """

        written = self._store.finish(
            task_id, status=TaskStatus.FAILED, stage="wait", error_code=None, label=None, decision=None,
        )
        if not written and self._store.cancel_accepted(task_id):
            self._store.finish(
                task_id, status=TaskStatus.CANCELLED, stage="wait", error_code=None, label=None, decision=None,
            )


async def drain(worker: SingleTaskWorker) -> int:
    """Process queued tasks until none is claimable; return how many ran.

    「领不到任务」不等于「队列已空」：一行仍在时限内的 ``RUNNING`` 就会让循环停下，
    而队列里可能还有 ``QUEUED``。返回后读 ``worker.stall`` 才能把两者分开，调用方
    不应假定本函数返回即意味着队列已排空（Issue #44 第 3.2 条）。
    """

    count = 0
    while await worker.run_once():
        count += 1
    return count


async def drain_forever(worker: SingleTaskWorker, interval: float) -> int:
    """Keep claiming tasks until the process is stopped; return how many ran.

    The API process never executes a task, so without a worker that stays up a
    queued task would sit in QUEUED while the client polls it. The loop only
    waits ``interval`` seconds when the queue is empty, so a busy queue is still
    drained back to back. Cancellation propagates out of ``asyncio.sleep``; how a
    console interrupt reaches the process differs by platform, so the entry point
    reports it instead of assuming a signal number.

    A failure that escapes ``run_once`` — a store read, or settling a task that
    already failed — must not end the process: without this guard the worker
    exits, and every later task stays QUEUED while the client keeps polling a
    service that will never run it. Such a task is left for the next startup
    sweep rather than reported as failed here, because this frame cannot tell
    which stage it reached. ``CancelledError`` inherits from ``BaseException``,
    so it still unwinds instead of being absorbed as a task failure.
    """

    count = 0
    while True:
        try:
            while await worker.run_once():
                count += 1
        except Exception:  # one task must not take the whole worker down with it
            logger.exception("Worker loop iteration failed; continuing")
        await asyncio.sleep(interval)
