"""Configured local gateway boundary. No SDK or upstream call is implemented."""

from typing import Protocol

from paper_evidence.domain.records import ModelReply


class ModelGateway(Protocol):
    async def complete(self, request_id: str, prompt: str, deadline: float) -> ModelReply: ...
