"""Single-process worker: one task at a time.

The worker drains queued tasks, one per claim. The total deadline starts when the
task is atomically claimed and becomes RUNNING; it covers source processing,
model calls, retry waits and validation but not queue time.
"""

import asyncio
import logging
import time

from paper_evidence.domain import ErrorCode, TaskStatus

__all__ = ["SingleTaskWorker", "drain"]

logger = logging.getLogger(__name__)


class SingleTaskWorker:
    def __init__(self, store, workflow_factory, settings) -> None:
        self._store = store
        self._workflow_factory = workflow_factory
        self._settings = settings

    async def run_once(self) -> bool:
        """Claim and process at most one task; return whether one was processed."""

        task_seconds = self._settings.timeouts.task_seconds
        # The run itself is bounded by a monotonic clock; the value persisted for
        # the API's expiry check is a wall-clock epoch (same clock, same duration).
        deadline = time.monotonic() + task_seconds
        task = await asyncio.to_thread(self._store.claim_next, time.time() + task_seconds)
        if task is None:
            return False
        workflow = self._workflow_factory(task)
        try:
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
    """Process queued tasks until the queue is empty; return how many ran."""

    count = 0
    while await worker.run_once():
        count += 1
    return count
