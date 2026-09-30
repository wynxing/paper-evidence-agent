"""Single-task worker boundary; no polling or task execution is implemented."""

from typing import Protocol


class TaskWorker(Protocol):
    async def run_once(self) -> bool:
        """Return whether a task was processed; implementation is pending."""
        ...
