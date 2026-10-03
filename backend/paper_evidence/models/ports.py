"""Configured local gateway boundary. No SDK or upstream call is implemented."""

from typing import Protocol

from paper_evidence.domain.records import ModelReply


class ModelGateway(Protocol):
    async def complete(self, request_id: str, prompt: str, deadline: float) -> ModelReply:
        """Complete one model request.

        deadline is an absolute time.monotonic() timestamp. Failures raise
        ContractError with UPSTREAM_TIMEOUT, UPSTREAM_RATE_LIMITED,
        UPSTREAM_AUTH_FAILED, UPSTREAM_INVALID_REQUEST, or UPSTREAM_UNAVAILABLE.
        TASK_TIMEOUT is the worker and workflow total deadline, not this call.
        """
        ...
