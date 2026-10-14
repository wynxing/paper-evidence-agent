"""Single-task worker boundary; no polling or task execution is implemented."""

from typing import Protocol


class TaskWorker(Protocol):
    async def run_once(self) -> bool:
        """Process at most one claimed task.

        Observe cancel_requested and the task's absolute monotonic deadline.
        An accepted cancellation finishes as CANCELLED and is not replaced by
        TASK_TIMEOUT. Settle provably dead leftovers before claiming, because a
        leftover RUNNING row now blocks claiming (Issue #34). Return whether a
        task was processed; ``False`` also covers "another worker is running the
        task that keeps the queue claimed". Implementation is pending.
        """
        ...
