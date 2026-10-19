"""Local trace recorder.

The diagnostic record lives in SQLite; this recorder writes it and nothing else.
Export is a separate concern in ``tracing/otel.py`` and stays off unless Langfuse
is configured, because its failures must never change a task result.
"""

from paper_evidence.domain.contracts import ExecutionRecord

__all__ = ["LocalTraceRecorder"]


class LocalTraceRecorder:
    def __init__(self, store) -> None:
        self._store = store

    def record(self, task_id: str, event: ExecutionRecord) -> None:
        self._store.record_execution(task_id, event)
