"""Shared bookkeeping for one logical model request.

Two transports can complete the same logical request: the in-process LiteLLM SDK
(``sdk.py``) and the OpenAI-compatible client for a configured gateway
(``gateway.py``). Both must produce the same record — the same ``params_digest``
for a failure as for a success, one attempt per actually dispatched request, an
attempt index starting at 1, and null rather than zero for anything unobserved.
Keeping that in one place is what stops the two transports from drifting apart
in the diagnosis packet.

Nothing here opens a socket or names a provider.
"""

import time

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.domain.contracts import ModelAttempt, ModelCall, TokenUsage
from paper_evidence.domain.digest import digest_of

__all__ = [
    "AttemptRecorder",
    "ModelFailure",
    "elapsed_ms",
    "status_error",
    "usage_from_mapping",
]


class ModelFailure(ContractError):
    """A failed logical request carrying the call record that must be stored.

    The recorder builds the record for both outcomes, so a failed attempt keeps
    the same ``params_digest`` as a successful one instead of reusing the
    request id.
    """

    def __init__(self, error_code: ErrorCode, call: ModelCall, message: str = "") -> None:
        super().__init__(error_code, message)
        self.call = call


def status_error(status: int) -> ErrorCode:
    """Map an upstream HTTP status to an independent upstream error code."""

    if status in (401, 403):
        return ErrorCode.UPSTREAM_AUTH_FAILED
    if status in (400, 404, 406, 415, 422):
        return ErrorCode.UPSTREAM_INVALID_REQUEST
    if status == 429:
        return ErrorCode.UPSTREAM_RATE_LIMITED
    if status >= 500:
        return ErrorCode.UPSTREAM_UNAVAILABLE
    return ErrorCode.UPSTREAM_INVALID_REQUEST


def usage_from_mapping(payload: object) -> TokenUsage | None:
    """Read usage from an OpenAI-compatible body. Absent usage stays null."""

    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    return usage_from_fields(usage)


def usage_from_fields(usage: object) -> TokenUsage | None:
    """Read usage off an object or mapping. Absent usage stays null."""

    if usage is None:
        return None

    def read(name: str) -> int | None:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        return value if isinstance(value, int) else None

    return TokenUsage(prompt_tokens=read("prompt_tokens"),
                      completion_tokens=read("completion_tokens"),
                      total_tokens=read("total_tokens"))


def elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


class AttemptRecorder:
    """Build the request and attempt records a transport has to hand back."""

    def __init__(self, *, model_alias: str, configured_model: str, deployment_id: str,
                 recipient: str, attempt_seconds: float) -> None:
        self.model_alias = model_alias
        self._configured_model = configured_model
        self._deployment_id = deployment_id
        self._recipient = recipient
        self._attempt_seconds = float(attempt_seconds)

    def remaining(self, deadline: float) -> float:
        """Time left on the task clock; an expired deadline is TASK_TIMEOUT.

        TASK_TIMEOUT is the worker's total deadline, not a model attempt, so it
        is raised without a call record.
        """

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ContractError(ErrorCode.TASK_TIMEOUT, "任务剩余时间不足")
        return remaining

    def timeout_for(self, deadline: float) -> float:
        """The per-attempt cap, never more than the task has left."""

        return min(self._attempt_seconds, self.remaining(deadline))

    def call_record(self, request_id: str, *, purpose: str, round_index: int | None,
                    prompt_version: str, context_paragraph_ids: list[str] | None,
                    repairs_request_id: str | None, attempts: list[ModelAttempt]) -> ModelCall:
        return ModelCall(
            request_id=request_id,
            purpose=purpose,
            round=round_index,
            model_alias=self.model_alias,
            prompt_version=prompt_version,
            params_digest=self.params_digest(),
            context_paragraph_ids=list(context_paragraph_ids or []),
            repairs_request_id=repairs_request_id,
            attempts=attempts,
        )

    def params_digest(self) -> str:
        """The redacted parameter digest, never the request id."""

        return digest_of({"model": self.model_alias, "temperature": 0, "stream": False, "cache": False})

    def attempt_record(self, request_id: str, *, error_code: ErrorCode | None, duration_ms: int,
                       attempt_index: int = 1, gateway_request_id: str | None = None,
                       upstream_response_id: str | None = None, response_model: str | None = None,
                       usage: TokenUsage | None = None, recovery_kind: str = "none",
                       recovery_reason: ErrorCode | None = None) -> ModelAttempt:
        """One dispatched upstream attempt, numbered from 1.

        The recovery fields belong to the attempt that *is* the recovery: the
        first one is ``none``, and a retried second one carries ``retry`` plus the
        error that triggered it (术语表「调用账与版本归属」).
        """

        return ModelAttempt(
            attempt_id=f"{request_id}:{attempt_index}",
            attempt_index=attempt_index,
            span_id=f"span:{request_id}:{attempt_index}",
            gateway_request_id=gateway_request_id,
            upstream_response_id=upstream_response_id,
            configured_model=self._configured_model,
            deployment_id=self._deployment_id,
            recipient=self._recipient,
            response_model=response_model,
            verified_model_version=None,
            recovery_kind=recovery_kind,  # type: ignore[arg-type]
            recovery_reason=recovery_reason,
            status="success" if error_code is None else "error",
            error_code=error_code,
            duration_ms=duration_ms,
            usage=usage,
        )
