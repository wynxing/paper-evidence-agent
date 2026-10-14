"""Local persistence boundary. SQLite/FTS5 is not implemented yet."""

from typing import Protocol

from paper_evidence.domain import TaskStatus
from paper_evidence.domain.contracts import CancelResponse, CheckDetail, CheckSummary, ConflictResponse
from paper_evidence.domain.records import TaskInput


class TaskRepository(Protocol):
    def create(self, task: TaskInput) -> None: ...

    def get(self, task_id: str) -> CheckDetail | None: ...

    def list(self, status: TaskStatus | None = None) -> list[CheckSummary]: ...

    def claim_next(self) -> TaskInput | None:
        """Atomically claim one queued task; None when none may be claimed.

        Returns None both when the queue is empty and when a task is still
        RUNNING: 「同一时刻只执行一个任务」是存储层不变量，不是只靠运行约定
        （Issue #34）。实现只能返回它在本次调用中真正领取的任务。
        """
        ...

    def request_cancel(self, task_id: str) -> CancelResponse | ConflictResponse | None:
        """Atomically record cancellation without replacing the whole detail.

        None when the task is missing. CancelResponse when cancellation is
        accepted or the task is already CANCELLED. ConflictResponse when
        another terminal state wins; the stored task stays unchanged.
        """
        ...

    def settle_orphaned_running(self) -> int:
        """Settle the leftover RUNNING tasks that cannot still be alive.

        Only a row whose wall-clock deadline has already passed is an orphan: the
        task's own time limit says it cannot still be executing. A row without a
        deadline also counts, because the claim path always records one. A task
        another worker is still running keeps its RUNNING row.

        A persisted cancel_requested becomes CANCELLED. Any other orphan becomes
        INTERRUPTED. Return how many tasks changed.
        """
        ...

    def save(self, result: CheckDetail) -> None:
        """Conditionally store a terminal result.

        Do not overwrite CANCELLED or another terminal state, including when
        cancellation was accepted after this result was prepared.
        """
        ...

    def delete(self, task_id: str) -> None: ...
