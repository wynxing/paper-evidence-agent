"""Local trace recorder.

The first version keeps a local OpenTelemetry-shaped trace in SQLite. Optional
Langfuse export is off by default and is not wired here: enabling it requires a
configured endpoint, credentials and a separately authorized observability
recipient, and its failures must never change a task result.
"""

from paper_evidence.domain.contracts import ExecutionRecord

__all__ = ["LocalTraceRecorder"]


class LocalTraceRecorder:
    def __init__(self, store) -> None:
        self._store = store

    def record(self, task_id: str, event: ExecutionRecord) -> None:
        self._store.record_execution(task_id, event)
