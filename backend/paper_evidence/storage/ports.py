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
        """Atomically claim one queued task; implementation is pending."""
        ...

    def request_cancel(self, task_id: str) -> CancelResponse | ConflictResponse | None:
        """Atomically record cancellation without replacing the whole detail.

        None when the task is missing. CancelResponse when cancellation is
        accepted or the task is already CANCELLED. ConflictResponse when
        another terminal state wins; the stored task stays unchanged.
        """
        ...

    def settle_orphaned_running(self) -> int:
        """On startup, settle leftover RUNNING tasks.

        A persisted cancel_requested becomes CANCELLED. Any other leftover
        RUNNING becomes INTERRUPTED. Return how many tasks changed.
        """
        ...

    def save(self, result: CheckDetail) -> None:
        """Conditionally store a terminal result.

        Do not overwrite CANCELLED or another terminal state, including when
        cancellation was accepted after this result was prepared.
        """
        ...

    def delete(self, task_id: str) -> None: ...
