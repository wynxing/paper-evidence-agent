"""Local execution-span recording for the workflow.

Spans record which step observed which input, output or error; they never claim
to explain the model's internal reasoning. Only identifiers, stages, tool names,
durations and error codes are stored — never claims, prompts or responses.
"""

import time

from paper_evidence.domain.contracts import ExecutionRecord

__all__ = ["StageRecorder"]


class StageRecorder:
    """Record one ``ExecutionRecord`` per workflow step and track the current stage."""

    def __init__(self, store, task_id: str, db) -> None:
        self._store = store
        self._task_id = task_id
        self._db = db
        self._seq = 0
        self.stage = None

    def _span(self) -> str:
        self._seq += 1
        return f"span:{self._task_id}:{self._seq}"

    async def enter(self, stage, tool: str) -> None:
        self.stage = stage

    async def ok(self, stage, tool: str, started: float, round_index=None, request_id=None) -> None:
        await self._record(stage, tool, "success", None, started, round_index, request_id)

    async def fail(self, stage, tool: str, error_code, started: float, round_index=None, request_id=None) -> None:
        await self._record(stage, tool, "error", error_code, started, round_index, request_id)

    async def _record(self, stage, tool, status, error_code, started, round_index, request_id) -> None:
        self.stage = stage
        event = ExecutionRecord(
            stage=stage,
            span_id=self._span(),
            tool=tool,
            status=status,
            error_code=error_code,
            duration_ms=int((time.monotonic() - started) * 1000),
            round=round_index,
            request_id=request_id,
        )
        await self._db(self._store.record_execution, self._task_id, event)
