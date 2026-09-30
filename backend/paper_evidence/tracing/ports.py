"""Local trace boundary; no collector or telemetry exporter is enabled."""

from typing import Protocol

from paper_evidence.domain.contracts import ExecutionRecord


class TraceRecorder(Protocol):
    def record(self, task_id: str, event: ExecutionRecord) -> None: ...
