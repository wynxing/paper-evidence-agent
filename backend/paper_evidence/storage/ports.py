"""Local persistence boundary. SQLite/FTS5 is not implemented yet."""

from typing import Protocol

from paper_evidence.domain import TaskStatus
from paper_evidence.domain.contracts import CheckDetail, CheckSummary
from paper_evidence.domain.records import TaskInput


class TaskRepository(Protocol):
    def create(self, task: TaskInput) -> None: ...

    def get(self, task_id: str) -> CheckDetail | None: ...

    def list(self, status: TaskStatus | None = None) -> list[CheckSummary]: ...

    def claim_next(self) -> TaskInput | None:
        """Atomically claim one queued task; implementation is pending."""
        ...

    def save(self, result: CheckDetail) -> None: ...

    def delete(self, task_id: str) -> None: ...
