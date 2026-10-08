"""Model gateway: routing shape, no client retries and upstream error mapping."""

import asyncio
import time

import httpx
import pytest

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.models.gateway import ModelFailure, OpenAIChatGateway


def build(handler, recipient="Agnes"):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAIChatGateway(
        client, base_url="https://gateway.test", token="token", model_alias="paper-default",
        configured_model="agnes-2.5-flash", deployment_id="agnes-primary", recipient=recipient,
        attempt_seconds=45,
    )


def complete(gateway, deadline=None):
    return asyncio.run(gateway.complete(
        "r1", "prompt", deadline if deadline is not None else time.monotonic() + 30,
        purpose="query_generation", round_index=0, prompt_version="v", context_paragraph_ids=["p:1"],
    ))


def test_success_records_one_attempt_and_keeps_unknown_fields_null():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer token"
        return httpx.Response(200, json={"id": "resp-1", "model": "agnes-2.5-flash",
                                         "choices": [{"message": {"content": '{"queries": ["a"]}'}}]})

    reply = complete(build(handler))
    assert reply.text == '{"queries": ["a"]}'
    call = reply.call
    assert call.purpose == "query_generation" and call.round == 0
    assert call.context_paragraph_ids == ["p:1"]
    attempt = call.attempts[0]
    assert attempt.status == "success"
    assert attempt.response_model == "agnes-2.5-flash"
    assert attempt.verified_model_version is None  # never the alias
    assert attempt.usage is None  # missing usage is null, not zero
    assert attempt.recipient == "Agnes"


def test_client_does_not_retry_a_transient_failure():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(429, headers={"retry-after": "1"}, json={})

    with pytest.raises(ModelFailure) as raised:
        complete(build(handler))
    assert raised.value.error_code is ErrorCode.UPSTREAM_RATE_LIMITED
    assert calls["n"] == 1  # recovery belongs to the Proxy, not the client
    attempt = raised.value.attempt
    assert attempt.status == "error" and attempt.recovery_kind == "none"
    assert attempt.error_code is ErrorCode.UPSTREAM_RATE_LIMITED


@pytest.mark.parametrize("status,code", [
    (401, ErrorCode.UPSTREAM_AUTH_FAILED),
    (400, ErrorCode.UPSTREAM_INVALID_REQUEST),
    (503, ErrorCode.UPSTREAM_UNAVAILABLE),
])
def test_http_status_maps_to_independent_upstream_codes(status, code):
    def handler(request):
        return httpx.Response(status, json={"error": "x"})

    with pytest.raises(ModelFailure) as raised:
        complete(build(handler))
    assert raised.value.error_code is code


def test_connection_error_is_upstream_unavailable():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ModelFailure) as raised:
        complete(build(handler))
    assert raised.value.error_code is ErrorCode.UPSTREAM_UNAVAILABLE


def test_timeout_is_upstream_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ModelFailure) as raised:
        complete(build(handler))
    assert raised.value.error_code is ErrorCode.UPSTREAM_TIMEOUT


def test_expired_deadline_is_task_timeout_not_an_attempt():
    with pytest.raises(ContractError) as raised:
        complete(build(lambda request: httpx.Response(200, json={})), deadline=time.monotonic() - 1)
    assert raised.value.error_code is ErrorCode.TASK_TIMEOUT


def test_malformed_success_body_is_invalid_request():
    def handler(request):
        return httpx.Response(200, content=b"not json", headers={"content-type": "application/json"})

    with pytest.raises(ModelFailure) as raised:
        complete(build(handler))
    assert raised.value.error_code is ErrorCode.UPSTREAM_INVALID_REQUEST
