"""Bounded workflow boundary. LangGraph nodes are not implemented yet."""

from typing import Protocol

from paper_evidence.domain.contracts import CheckDetail
from paper_evidence.domain.records import TaskInput


class VerificationWorkflow(Protocol):
    async def run(self, task: TaskInput, deadline: float) -> CheckDetail:
        """Run one claimed task until a terminal detail.

        deadline is an absolute time.monotonic() timestamp for the whole task.
        Reaching it raises ContractError(TASK_TIMEOUT) unless cancellation was
        already accepted; an accepted cancel is not rewritten. Budget, output,
        and quote failures use BUDGET_EXCEEDED, MODEL_INVALID_OUTPUT, and
        QUOTE_MISMATCH.
        """
        ...
