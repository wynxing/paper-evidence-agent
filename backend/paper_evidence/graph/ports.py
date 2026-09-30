"""Bounded workflow boundary. LangGraph nodes are not implemented yet."""

from typing import Protocol

from paper_evidence.domain.contracts import CheckDetail
from paper_evidence.domain.records import TaskInput


class VerificationWorkflow(Protocol):
    async def run(self, task: TaskInput, deadline: float) -> CheckDetail: ...
