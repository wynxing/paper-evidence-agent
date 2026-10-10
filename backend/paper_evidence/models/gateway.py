"""OpenAI-compatible model client for the local LiteLLM Proxy.

Business code only ever uses the model alias; upstream addresses, keys and
mappings live in the Proxy. Client-side retries are disabled, so network
recovery belongs to the Proxy and structural output repair belongs to the
workflow. Each logical request records the attempts actually dispatched, keyed
by ``request_id``; a missing gateway/upstream id or version stays ``null`` and
usage is never padded with zero.
"""

import time

import httpx

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.domain.contracts import ModelAttempt, ModelCall, TokenUsage
from paper_evidence.domain.digest import digest_of
from paper_evidence.domain.records import ModelReply

__all__ = ["ModelFailure", "OpenAIChatGateway"]


class ModelFailure(ContractError):
    """A failed logical request carrying the call record that must be stored.

    The gateway builds the record for both outcomes, so a failed attempt keeps
    the same ``params_digest`` as a successful one instead of reusing the
    request id.
    """

    def __init__(self, error_code: ErrorCode, call: ModelCall, message: str = "") -> None:
        super().__init__(error_code, message)
        self.call = call


def _status_error(status: int) -> ErrorCode:
    if status in (401, 403):
        return ErrorCode.UPSTREAM_AUTH_FAILED
    if status in (400, 404, 406, 415, 422):
        return ErrorCode.UPSTREAM_INVALID_REQUEST
    if status == 429:
        return ErrorCode.UPSTREAM_RATE_LIMITED
    if status >= 500:
        return ErrorCode.UPSTREAM_UNAVAILABLE
    return ErrorCode.UPSTREAM_INVALID_REQUEST


def _usage(payload: dict) -> TokenUsage | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    return TokenUsage(
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
    )


class OpenAIChatGateway:
    """Complete one logical request through the configured Proxy."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str,
        token: str | None,
        model_alias: str,
        configured_model: str,
        deployment_id: str,
        recipient: str,
        attempt_seconds: float,
    ) -> None:
        self._client = client
        self._base = base_url.rstrip("/")
        self._token = token
        self._alias = model_alias
        self._configured_model = configured_model
        self._deployment_id = deployment_id
        self._recipient = recipient
        self._attempt_seconds = float(attempt_seconds)

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ContractError(ErrorCode.TASK_TIMEOUT, "任务剩余时间不足")
        return remaining

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
        attempt_span = f"span:{request_id}:1"
        attempt_id = f"{request_id}:1"
        started = time.monotonic()
        timeout = min(self._attempt_seconds, self._remaining(deadline))
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        body = {
            "model": self._alias,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
            "cache": {"no-cache": True},
        }

        def call(attempts: list[ModelAttempt]) -> ModelCall:
            """One logical request record, shared by the success and failure paths."""

            return ModelCall(
                request_id=request_id,
                purpose=purpose,
                round=round_index,
                model_alias=self._alias,
                prompt_version=prompt_version,
                params_digest=digest_of({"model": self._alias, "temperature": 0, "stream": False, "cache": False}),
                context_paragraph_ids=list(context_paragraph_ids or []),
                repairs_request_id=repairs_request_id,
                attempts=attempts,
            )

        def attempt(error_code: ErrorCode | None, payload: dict | None, duration_ms: int,
                    response: httpx.Response | None = None) -> ModelAttempt:
            return ModelAttempt(
                attempt_id=attempt_id,
                attempt_index=1,
                span_id=attempt_span,
                gateway_request_id=(response.headers.get("x-litellm-call-id") or response.headers.get("x-request-id"))
                if response is not None else None,
                upstream_response_id=(payload or {}).get("id"),
                configured_model=self._configured_model,
                deployment_id=self._deployment_id,
                recipient=self._recipient,
                response_model=(payload or {}).get("model"),
                verified_model_version=None,
                recovery_kind="none",
                recovery_reason=None,
                status="success" if error_code is None else "error",
                error_code=error_code,
                duration_ms=duration_ms,
                usage=_usage(payload or {}),
            )

        try:
            response = await self._client.post(
                f"{self._base}/v1/chat/completions", json=body, headers=headers, timeout=timeout
            )
        except httpx.TimeoutException:
            raise ModelFailure(ErrorCode.UPSTREAM_TIMEOUT,
                               call([attempt(ErrorCode.UPSTREAM_TIMEOUT, None, _ms(started))]))
        except (httpx.ConnectError, httpx.TransportError, httpx.RemoteProtocolError):
            raise ModelFailure(ErrorCode.UPSTREAM_UNAVAILABLE,
                               call([attempt(ErrorCode.UPSTREAM_UNAVAILABLE, None, _ms(started))]))

        if response.status_code != 200:
            code = _status_error(response.status_code)
            raise ModelFailure(code, call([attempt(code, None, _ms(started), response)]))

        try:
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ModelFailure(
                ErrorCode.UPSTREAM_INVALID_REQUEST,
                call([attempt(ErrorCode.UPSTREAM_INVALID_REQUEST, None, _ms(started), response)]),
            )

        return ModelReply(text=text if isinstance(text, str) else str(text),
                          call=call([attempt(None, payload, _ms(started), response)]))


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
