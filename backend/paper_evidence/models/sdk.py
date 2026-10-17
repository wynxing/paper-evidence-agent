"""In-process LiteLLM SDK transport for one model request.

LiteLLM runs either as a gateway process or as a library inside this one. This
is the library form and the default: no second service to start, no port to
reserve, no gateway configuration file to keep in step with the application.

What the gateway form was chosen for is kept, not dropped:

* business code still names only the alias ``paper-default``; the alias-to-model
  mapping is configuration, and provider adaptation stays inside LiteLLM instead
  of being reimplemented here;
* one logical request still records the attempts actually dispatched, and the
  call id a gateway would report in ``x-litellm-call-id`` is read from
  ``ModelResponse._hidden_params["litellm_call_id"]`` instead;
* the bounded recovery a gateway used to own happens here instead, on the same
  deployment, and both attempts are recorded (``recovery_kind="retry"``).

What changes: upstream credentials are read by this process rather than by a
gateway, so a deployment that needs them held elsewhere configures the gateway
transport instead. Cross-deployment fallback is not implemented by either
transport: nothing in the configuration names a fallback deployment.
"""

import asyncio
import os

# Set before LiteLLM is imported: it otherwise downloads its model cost map at
# import time. This project reports cost as unknown, so that download buys
# nothing but latency, and with no route out it costs a retry first.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import time  # noqa: E402

import litellm  # noqa: E402
from litellm import exceptions as litellm_errors  # noqa: E402

from paper_evidence.domain import ErrorCode  # noqa: E402
from paper_evidence.domain.contracts import ModelAttempt, ModelCall  # noqa: E402
from paper_evidence.domain.records import ModelReply  # noqa: E402
from paper_evidence.domain.rules import RECOVERY_BACKOFF_SECONDS  # noqa: E402
from paper_evidence.models.recording import (  # noqa: E402
    AttemptRecorder,
    ModelFailure,
    elapsed_ms,
    usage_from_fields,
)

__all__ = ["LiteLLMSdkGateway", "NOT_UPSTREAM_FAILURES", "RECOVERABLE_CODES", "error_code_for"]

# D6 forbids the gateway and the application from logging claim text, prompts,
# responses or keys. The SDK defaults both switches the other way, and it prints
# a support block on every failure unless debug info is suppressed.
litellm.suppress_debug_info = True
litellm.turn_off_message_logging = True

# Only these are worth another attempt: a transient network or capacity problem.
# Authentication, parameter errors and an unparsable completion are not, and a
# completion the workflow could not parse is repaired by the workflow, not here.
RECOVERABLE_CODES = frozenset({
    ErrorCode.UPSTREAM_TIMEOUT,
    ErrorCode.UPSTREAM_UNAVAILABLE,
    ErrorCode.UPSTREAM_RATE_LIMITED,
})

# LiteLLM's root HTTP failure class. Its own ``APIError`` is a subclass of this,
# but several of its exceptions — ``BadGatewayError`` and ``InvalidRequestError``
# among them — derive from the ``openai`` base directly. A table that named only
# LiteLLM's classes would let those through unmapped, and an unmapped failure
# reaches the worker as ``error_code: null``. The ancestor is taken off LiteLLM
# rather than by importing ``openai``, which is not a declared dependency here.
_OPENAI_API_ERROR: type[BaseException] = next(
    base for base in litellm_errors.APIError.__mro__ if base.__module__.split(".")[0] == "openai"
)

# Checked in order, and the order is load bearing: LiteLLM maps provider
# timeouts to its own ``Timeout``, which extends ``APITimeoutError``, which
# extends ``APIConnectionError``, and every status error is an ``APIError``. A
# broader entry placed first would swallow the narrower ones. LiteLLM wraps
# provider failures into these classes in ``exception_mapping_utils``.
_ERROR_CODES: tuple[tuple[tuple[type[BaseException], ...], ErrorCode], ...] = (
    ((litellm_errors.Timeout,), ErrorCode.UPSTREAM_TIMEOUT),
    ((litellm_errors.APIConnectionError, litellm_errors.BadGatewayError),
     ErrorCode.UPSTREAM_UNAVAILABLE),
    ((litellm_errors.AuthenticationError, litellm_errors.PermissionDeniedError),
     ErrorCode.UPSTREAM_AUTH_FAILED),
    ((litellm_errors.RateLimitError,), ErrorCode.UPSTREAM_RATE_LIMITED),
    ((litellm_errors.BadRequestError, litellm_errors.InvalidRequestError,
      litellm_errors.NotFoundError, litellm_errors.UnprocessableEntityError),
     ErrorCode.UPSTREAM_INVALID_REQUEST),
    # A response LiteLLM itself could not read as a completion is as unusable as
    # one whose choice list is missing, which the transport maps the same way.
    ((litellm_errors.APIResponseValidationError,), ErrorCode.UPSTREAM_INVALID_REQUEST),
    ((litellm_errors.InternalServerError, litellm_errors.ServiceUnavailableError),
     ErrorCode.UPSTREAM_UNAVAILABLE),
    ((_OPENAI_API_ERROR,), ErrorCode.UPSTREAM_UNAVAILABLE),
)

# Failures of LiteLLM's own control plane — a misconfiguration or a feature this
# project never enables — rather than a response from the upstream. They stay
# unmapped on purpose so they surface as an execution error with a logged
# traceback instead of being reported as an upstream outage.
NOT_UPSTREAM_FAILURES: tuple[type[BaseException], ...] = (
    litellm_errors.OpenAIError,
    litellm_errors.BlockedPiiEntityError,
    litellm_errors.BudgetExceededError,
    litellm_errors.GuardrailRaisedException,
    litellm_errors.ModelNotMappedError,
    litellm_errors.ModifyResponseException,
    litellm_errors.MockException,
    litellm_errors.SensitiveDataRouteException,
)

# A new LiteLLM release can add a failure class, and the transport would let it
# through unmapped. tests/tools/test_sdk_gateway.py walks every class in
# ``litellm.exceptions`` and fails unless it is matched by ``_ERROR_CODES`` or
# listed above, so the table below cannot rot silently across a version bump.


def error_code_for(error: BaseException) -> ErrorCode | None:
    """Map a LiteLLM failure to its upstream code; unrecognized stays None."""

    for classes, code in _ERROR_CODES:
        if isinstance(error, classes):
            return code
    return None


def _field(response: object, name: str) -> str | None:
    value = getattr(response, name, None)
    return value if isinstance(value, str) and value else None


def _call_id(response: object) -> str | None:
    """The LiteLLM call id, kept where a gateway would have sent a header."""

    hidden = getattr(response, "_hidden_params", None)
    if not isinstance(hidden, dict):
        return None
    call_id = hidden.get("litellm_call_id")
    if call_id:
        return str(call_id)
    headers = hidden.get("additional_headers")
    if isinstance(headers, dict) and headers.get("x-request-id"):
        return str(headers["x-request-id"])
    return None


def _retry_after_seconds(error: BaseException) -> float | None:
    """The wait the upstream asked for, in seconds; ``None`` when it asked for none.

    Only the delta-seconds form is honoured. An HTTP-date form would need a
    wall-clock comparison inside a deadline that is deliberately monotonic, so it
    is read as no requested wait rather than as an unknown one.

    ``None`` and ``0.0`` are deliberately different: no header means "the caller
    must choose a wait" (``RECOVERY_BACKOFF_SECONDS``), while ``Retry-After: 0``
    is the upstream saying "now" and is taken literally (Issue #69).
    """

    get = getattr(getattr(error, "response", None), "headers", None)
    raw = get.get("retry-after") if hasattr(get, "get") else None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def _content(response: object) -> str:
    """The completion text; a response without one is not a usable answer."""

    text = response.choices[0].message.content
    return text if isinstance(text, str) else str(text)


class LiteLLMSdkGateway(AttemptRecorder):
    """Complete one logical request with LiteLLM running inside this process."""

    def __init__(
        self,
        *,
        provider_model: str,
        api_base: str,
        api_key: str | None,
        model_alias: str,
        configured_model: str,
        deployment_id: str,
        recipient: str,
        attempt_seconds: float,
        attempts_per_request: int = 2,
        completion=None,
    ) -> None:
        super().__init__(
            model_alias=model_alias, configured_model=configured_model, provider_model=provider_model,
            deployment_id=deployment_id, recipient=recipient, attempt_seconds=attempt_seconds,
        )
        self._provider_model = provider_model
        self._api_base = api_base
        self._api_key = api_key
        self._attempts = max(1, int(attempts_per_request))
        # Injectable so the record and error mapping can be tested without a
        # network call; the default is the SDK entry point.
        self._completion = completion or litellm.acompletion

    def _request(self, prompt: str, timeout: float) -> dict[str, object]:
        request: dict[str, object] = {
            "model": self._provider_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
            # The SDK must not add recovery of its own: the loop below is the only
            # recovery, so its budget stays observable and countable.
            "num_retries": 0,
            "timeout": timeout,
        }
        if self._api_base:
            request["api_base"] = self._api_base
        if self._api_key:
            request["api_key"] = self._api_key
        return request

    async def complete(
        self,
        request_id: str,
        prompt: str,
        deadline: float,
        *,
        purpose: str = "query_generation",
        round_index: int | None = None,
        prompt_version: str = "",
        context_paragraph_ids: list[str] | None = None,
        repairs_request_id: str | None = None,
    ) -> ModelReply:
        attempts: list[ModelAttempt] = []
        attempt_index = 1
        recovery_kind: str = "none"
        recovery_reason: ErrorCode | None = None

        def call() -> ModelCall:
            """One logical request record, over the attempts dispatched so far."""

            return self.call_record(
                request_id, purpose=purpose, round_index=round_index, prompt_version=prompt_version,
                context_paragraph_ids=context_paragraph_ids, repairs_request_id=repairs_request_id,
                attempts=list(attempts),
            )

        while True:
            timeout = self.timeout_for(deadline)
            started = time.monotonic()
            try:
                response = await self._completion(**self._request(prompt, timeout))
            except Exception as error:
                # A cancelled task arrives as CancelledError, a BaseException that
                # never reaches this handler, so cancellation is never retried.
                code = error_code_for(error)
                if code is None:
                    raise
                attempts.append(self.attempt_record(
                    request_id, error_code=code, duration_ms=elapsed_ms(started),
                    attempt_index=attempt_index, recovery_kind=recovery_kind,
                    recovery_reason=recovery_reason,
                ))
                if attempt_index >= self._attempts or code not in RECOVERABLE_CODES:
                    raise ModelFailure(code, call()) from None
                # Recovery needs a whole attempt of the task's remaining time; a
                # task that is out of time ends on its own deadline instead.
                remaining = self.remaining(deadline)
                requested = _retry_after_seconds(error)
                # No Retry-After must not mean "immediately" — the upstream is
                # throttling or failing, so wait the documented minimum (Issue #69).
                wait = RECOVERY_BACKOFF_SECONDS if requested is None else requested
                if wait >= remaining:
                    raise ModelFailure(code, call()) from None
                if wait:
                    await asyncio.sleep(min(wait, remaining))
                attempt_index += 1
                recovery_kind, recovery_reason = "retry", code
                continue

            try:
                text = _content(response)
            except (AttributeError, IndexError, TypeError):
                attempts.append(self.attempt_record(
                    request_id, error_code=ErrorCode.UPSTREAM_INVALID_REQUEST,
                    duration_ms=elapsed_ms(started), attempt_index=attempt_index,
                    recovery_kind=recovery_kind, recovery_reason=recovery_reason,
                ))
                raise ModelFailure(ErrorCode.UPSTREAM_INVALID_REQUEST, call()) from None

            attempts.append(self.attempt_record(
                request_id, error_code=None, duration_ms=elapsed_ms(started),
                attempt_index=attempt_index, recovery_kind=recovery_kind, recovery_reason=recovery_reason,
                gateway_request_id=_call_id(response),
                upstream_response_id=_field(response, "id"),
                response_model=_field(response, "model"),
                usage=usage_from_fields(getattr(response, "usage", None)),
            ))
            return ModelReply(text=text, call=call())
