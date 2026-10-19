"""Trace boundaries.

``TraceRecorder`` is the local record port; the OpenTelemetry sink lives in
``tracing/otel.py`` and is only built when Langfuse export is configured.
"""

from typing import Protocol

from paper_evidence.domain.contracts import ExecutionRecord


class TraceRecorder(Protocol):
    def record(self, task_id: str, event: ExecutionRecord) -> None: ...
