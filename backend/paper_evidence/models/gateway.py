"""OpenAI-compatible model client for a configured LiteLLM gateway.

One of two transports; ``sdk.py`` is the default in-process one. Choose this one
when a gateway process is available and the deployment wants upstream keys to
stay out of the application environment.

Business code only ever uses the model alias; upstream addresses, keys and
mappings live in the gateway. Client-side retries are disabled, so network
recovery belongs to the gateway and structural output repair belongs to the
workflow. Each logical request records the attempts actually dispatched, keyed
by ``request_id``; a missing gateway/upstream id or version stays ``null`` and
usage is never padded with zero.
"""

import time

import httpx

from paper_evidence.domain import ErrorCode
from paper_evidence.domain.contracts import ModelAttempt, ModelCall
from paper_evidence.domain.records import ModelReply
from paper_evidence.models.recording import (
    AttemptRecorder,
    ModelFailure,
    elapsed_ms,
    status_error,
    usage_from_mapping,
)

__all__ = ["ModelFailure", "OpenAIChatGateway"]


class OpenAIChatGateway(AttemptRecorder):
    """Complete one logical request through the configured gateway."""

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
        super().__init__(
            model_alias=model_alias, configured_model=configured_model, deployment_id=deployment_id,
            recipient=recipient, attempt_seconds=attempt_seconds,
        )
        self._client = client
        self._base = base_url.rstrip("/")
        self._token = token

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
        started = time.monotonic()
        timeout = self.timeout_for(deadline)
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        body = {
            "model": self.model_alias,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
            "cache": {"no-cache": True},
        }

        def call(attempts: list[ModelAttempt]) -> ModelCall:
            """One logical request record, shared by the success and failure paths."""

            return self.call_record(
                request_id, purpose=purpose, round_index=round_index, prompt_version=prompt_version,
                context_paragraph_ids=context_paragraph_ids, repairs_request_id=repairs_request_id,
                attempts=attempts,
            )

        def attempt(error_code: ErrorCode | None, payload: dict | None, duration_ms: int,
                    response: httpx.Response | None = None) -> ModelAttempt:
            return self.attempt_record(
                request_id, error_code=error_code, duration_ms=duration_ms,
                gateway_request_id=(response.headers.get("x-litellm-call-id") or response.headers.get("x-request-id"))
                if response is not None else None,
                upstream_response_id=(payload or {}).get("id"),
                response_model=(payload or {}).get("model"),
                usage=usage_from_mapping(payload),
            )

        try:
            response = await self._client.post(
                f"{self._base}/v1/chat/completions", json=body, headers=headers, timeout=timeout
            )
        except httpx.TimeoutException:
            raise ModelFailure(ErrorCode.UPSTREAM_TIMEOUT,
                               call([attempt(ErrorCode.UPSTREAM_TIMEOUT, None, elapsed_ms(started))]))
        except (httpx.ConnectError, httpx.TransportError, httpx.RemoteProtocolError):
            raise ModelFailure(ErrorCode.UPSTREAM_UNAVAILABLE,
                               call([attempt(ErrorCode.UPSTREAM_UNAVAILABLE, None, elapsed_ms(started))]))

        if response.status_code != 200:
            code = status_error(response.status_code)
            raise ModelFailure(code, call([attempt(code, None, elapsed_ms(started), response)]))

        try:
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ModelFailure(
                ErrorCode.UPSTREAM_INVALID_REQUEST,
                call([attempt(ErrorCode.UPSTREAM_INVALID_REQUEST, None, elapsed_ms(started), response)]),
            )

        return ModelReply(text=text if isinstance(text, str) else str(text),
                          call=call([attempt(None, payload, elapsed_ms(started), response)]))
