"""Model boundary. Two transports implement it; neither leaks into the workflow."""

from typing import Protocol

from paper_evidence.domain.records import ModelReply


class ModelGateway(Protocol):
    async def complete(self, request_id: str, prompt: str, deadline: float) -> ModelReply:
        """Complete one model request.

        deadline is an absolute time.monotonic() timestamp. Failures raise
        ContractError with UPSTREAM_TIMEOUT, UPSTREAM_RATE_LIMITED,
        UPSTREAM_AUTH_FAILED, UPSTREAM_INVALID_REQUEST, or UPSTREAM_UNAVAILABLE.
        TASK_TIMEOUT is the worker and workflow total deadline, not this call.

        Implemented by ``models/sdk.py`` (LiteLLM in this process, the default)
        and ``models/gateway.py`` (OpenAI-compatible client for a configured
        gateway). Both record attempts identically, so the workflow cannot tell
        which transport it was given. Bounded upstream recovery belongs to the
        transport: the workflow only repairs output and never retries the network.
        """
        ...
