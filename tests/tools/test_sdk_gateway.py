"""LiteLLM SDK transport: record shape, error mapping and no client retries."""

import asyncio
import os
import time

import httpx
import pytest

# Imported through the transport module rather than straight from litellm: that
# module sets LITELLM_LOCAL_MODEL_COST_MAP before LiteLLM loads, and importing
# LiteLLM first would make it download a cost map during the test run.
from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.domain.rules import RECOVERY_BACKOFF_SECONDS
from paper_evidence.models import sdk as sdk_module
from paper_evidence.models.recording import AttemptCancelled, ModelFailure
from paper_evidence.models.sdk import LiteLLMSdkGateway, error_code_for

litellm_errors = sdk_module.litellm.exceptions


class _Usage:
    prompt_tokens = 10
    completion_tokens = 20
    total_tokens = 30


class _Response:
    """The parts of a litellm ModelResponse the gateway reads."""

    def __init__(self, content='{"queries": ["a"]}', *, response_id="chatcmpl-1",
                 model="agnes-2.5-flash", usage=None, call_id="call-1", choices=True):
        self.id = response_id
        self.model = model
        self.usage = usage
        self._hidden_params = {"litellm_call_id": call_id} if call_id else {}
        self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()] if choices else []


def sdk_error(name):
    """Build a real LiteLLM exception; the base classes differ in what they take."""

    error_class = getattr(litellm_errors, name)
    status = 403 if name == "PermissionDeniedError" else 400
    response = httpx.Response(status, request=httpx.Request("POST", "https://models.test/v1/chat/completions"))
    try:
        return error_class(message="x", model="m", llm_provider="openai", response=response)
    except TypeError:
        return error_class(message="x", model="m", llm_provider="openai")


def rate_limited(retry_after=None):
    headers = {"retry-after": str(retry_after)} if retry_after is not None else None
    return litellm_errors.RateLimitError(
        message="slow down", model="m", llm_provider="openai",
        response=httpx.Response(429, headers=headers,
                                request=httpx.Request("POST", "https://models.test/v1/chat/completions")),
    )


def upstream_refused():
    """What LiteLLM raises when it cannot reach the provider at all.

    ``BadGatewayError`` extends the ``openai`` status base directly rather than
    LiteLLM's own ``APIError``, which is how it escaped an earlier mapping table
    and reached the worker as an unclassified failure with a null error code.
    """

    return litellm_errors.BadGatewayError(
        message="upstream connect failed", model="m", llm_provider="openai",
        response=httpx.Response(502, request=httpx.Request("POST", "https://models.test/v1/chat/completions")),
    )


def succeeding(response=None):
    async def completion(**kwargs):
        return response if response is not None else _Response()

    return completion


def failing(error):
    async def completion(**kwargs):
        raise error

    return completion


def flaky(errors, response=None):
    """Fail with each error in turn, then succeed."""

    pending = list(errors)

    async def completion(**kwargs):
        if pending:
            raise pending.pop(0)
        return response if response is not None else _Response()

    return completion


def slow_failure(error, delay):
    async def completion(**kwargs):
        await asyncio.sleep(delay)
        raise error

    return completion


def capturing():
    """Record the keyword arguments the gateway hands the SDK."""

    seen = {}

    async def completion(**kwargs):
        seen.update(kwargs)
        return _Response()

    return seen, completion


def build(completion=None, *, recipient="Agnes", api_base="https://models.test/v1", api_key="k",
          provider_model="openai/agnes-2.5-flash"):
    return LiteLLMSdkGateway(
        provider_model=provider_model, api_base=api_base, api_key=api_key,
        model_alias="paper-default", configured_model="agnes-2.5-flash", deployment_id="agnes-primary",
        recipient=recipient, attempt_seconds=45, completion=completion,
    )


def complete(gateway, deadline=None):
    return asyncio.run(gateway.complete(
        "r1", "prompt", deadline if deadline is not None else time.monotonic() + 300,
        purpose="query_generation", round_index=0, prompt_version="v", context_paragraph_ids=["p:1"],
    ))


@pytest.mark.parametrize("name", ["Timeout", "APIConnectionError", "AuthenticationError",
                                  "PermissionDeniedError", "RateLimitError", "BadRequestError",
                                  "NotFoundError", "UnprocessableEntityError", "InternalServerError",
                                  "ServiceUnavailableError"])
def test_every_litellm_failure_class_maps_to_an_upstream_code(name):
    """Otherwise swapping the transport would silently change the reported failure."""

    assert error_code_for(sdk_error(name)) is not None


def test_a_timeout_is_not_read_as_a_connection_failure():
    """``Timeout`` extends ``APIConnectionError``, so the table order decides this."""

    assert error_code_for(sdk_error("Timeout")) is ErrorCode.UPSTREAM_TIMEOUT
    assert error_code_for(sdk_error("APIConnectionError")) is ErrorCode.UPSTREAM_UNAVAILABLE


def test_every_litellm_failure_class_is_either_mapped_or_deliberately_not():
    """A LiteLLM upgrade must not quietly add a failure that nothing maps.

    An unmapped failure is re-raised unchanged and reaches the worker with a
    null error code, so an upstream outage would read as an unclassified bug.
    This walks LiteLLM's own namespace instead of a hand-kept list, so the
    table cannot rot across a version bump without a failing test.
    """

    classes = {
        name: value for name, value in vars(litellm_errors).items()
        if isinstance(value, type) and issubclass(value, BaseException)
    }
    assert classes  # an empty namespace would make the walk below vacuous
    unmapped = sorted(
        name for name, cls in classes.items()
        if not any(issubclass(cls, group) for group, _ in sdk_module._ERROR_CODES)
        and not issubclass(cls, sdk_module.NOT_UPSTREAM_FAILURES)
    )
    assert unmapped == []


def test_a_provider_that_refuses_the_connection_is_an_upstream_outage():
    """The regression that motivated the namespace-wide test above."""

    with pytest.raises(ModelFailure) as raised:
        complete(build(failing(upstream_refused())))
    assert raised.value.error_code is ErrorCode.UPSTREAM_UNAVAILABLE
    assert [attempt.error_code for attempt in raised.value.call.attempts] == [
        ErrorCode.UPSTREAM_UNAVAILABLE, ErrorCode.UPSTREAM_UNAVAILABLE
    ]
    assert raised.value.call.attempts[1].recovery_kind == "retry"


def test_success_records_the_call_id_the_sdk_would_have_sent_as_a_header():
    reply = complete(build(succeeding(_Response(usage=_Usage()))))
    assert reply.text == '{"queries": ["a"]}'
    call = reply.call
    assert call.purpose == "query_generation" and call.round == 0
    assert call.context_paragraph_ids == ["p:1"]
    assert call.model_alias == "paper-default"
    attempt = call.attempts[0]
    assert attempt.attempt_index == 1 and attempt.status == "success"
    assert attempt.gateway_request_id == "call-1"
    assert attempt.upstream_response_id == "chatcmpl-1"
    assert attempt.response_model == "agnes-2.5-flash"
    assert attempt.provider_model == "openai/agnes-2.5-flash"
    assert attempt.verified_model_version is None  # never the alias
    assert attempt.recipient == "Agnes"
    assert attempt.usage is not None and attempt.usage.total_tokens == 30


def test_missing_usage_and_missing_ids_stay_null_rather_than_zero():
    attempt = complete(build(succeeding(_Response(usage=None, call_id=None)))).call.attempts[0]
    assert attempt.usage is None
    assert attempt.gateway_request_id is None


def test_the_wire_payload_uses_the_configured_mapping_not_the_alias():
    seen, completion = capturing()
    complete(build(completion))
    assert seen["model"] == "openai/agnes-2.5-flash"
    assert seen["temperature"] == 0 and seen["stream"] is False
    assert seen["api_base"] == "https://models.test/v1" and seen["api_key"] == "k"


def test_the_attempt_records_the_model_the_sdk_actually_dispatches():
    """记录里的模型名必须与实际发出去的那个一致（Issue #68）。

    只写常量 `configured_model` 时，换上游后这条尝试记录一个字节都不会变，诊断包
    也就答不出「这次到底调了哪个模型」——只有上游回报的 `response_model` 是变的，
    而它取决于上游是否如实回传。本用例把记录与线上载荷绑在一起：两处只能改一起。
    """

    seen, completion = capturing()
    attempt = complete(build(completion, provider_model="deepseek/deepseek-flash")).call.attempts[0]
    assert attempt.provider_model == seen["model"] == "deepseek/deepseek-flash"
    assert attempt.configured_model == "agnes-2.5-flash"  # 常量：换上游不会变


def test_client_side_recovery_stays_off():
    seen, completion = capturing()
    complete(build(completion))
    assert seen["num_retries"] == 0


def test_unset_endpoint_and_key_are_not_sent_at_all():
    seen, completion = capturing()
    complete(build(completion, api_base="", api_key=None))
    assert "api_base" not in seen and "api_key" not in seen


def test_the_attempt_cap_is_never_more_than_the_task_has_left():
    seen, completion = capturing()
    complete(build(completion), deadline=time.monotonic() + 3)
    assert 0 < seen["timeout"] <= 3
    seen, completion = capturing()
    complete(build(completion))
    assert seen["timeout"] == 45  # the per-attempt cap when the task has longer


def test_failed_and_successful_calls_share_the_params_digest():
    """失败路径写的是脱敏参数摘要，不是 request id。"""

    reply = complete(build(succeeding()))
    with pytest.raises(ModelFailure) as raised:
        complete(build(failing(sdk_error("AuthenticationError"))))
    failure = raised.value.call
    assert failure.params_digest == reply.call.params_digest
    assert failure.params_digest != "r1"
    assert len(failure.attempts) == 1
    attempt = failure.attempts[0]
    assert attempt.status == "error" and attempt.recovery_kind == "none"
    assert attempt.error_code is ErrorCode.UPSTREAM_AUTH_FAILED
    assert attempt.usage is None


def test_a_recoverable_failure_is_retried_once_and_both_attempts_are_recorded():
    """The proxy used to own this. With no proxy, the transport has to."""

    with pytest.raises(ModelFailure) as raised:
        complete(build(failing(rate_limited())))
    failure = raised.value.call
    assert [attempt.attempt_index for attempt in failure.attempts] == [1, 2]
    first, second = failure.attempts
    assert (first.recovery_kind, first.recovery_reason) == ("none", None)
    assert (second.recovery_kind, second.recovery_reason) == ("retry", ErrorCode.UPSTREAM_RATE_LIMITED)
    assert [attempt.status for attempt in failure.attempts] == ["error", "error"]
    assert raised.value.error_code is ErrorCode.UPSTREAM_RATE_LIMITED
    assert [attempt.attempt_id for attempt in failure.attempts] == ["r1:1", "r1:2"]


def test_a_recovered_attempt_succeeds_with_the_first_failure_still_recorded():
    """A recovered error stays visible; it does not turn the task into a failure."""

    reply = complete(build(flaky([sdk_error("Timeout")])))
    assert reply.text == '{"queries": ["a"]}'
    assert [attempt.status for attempt in reply.call.attempts] == ["error", "success"]
    second = reply.call.attempts[1]
    assert (second.recovery_kind, second.recovery_reason) == ("retry", ErrorCode.UPSTREAM_TIMEOUT)
    assert second.gateway_request_id == "call-1"


def test_a_failure_that_is_not_recoverable_is_not_retried():
    calls = {"n": 0}

    async def counting(**kwargs):
        calls["n"] += 1
        raise sdk_error("BadRequestError")

    with pytest.raises(ModelFailure) as raised:
        complete(build(counting))
    assert calls["n"] == 1
    assert len(raised.value.call.attempts) == 1


def test_recovery_stops_at_the_configured_budget():
    calls = {"n": 0}

    async def counting(**kwargs):
        calls["n"] += 1
        raise rate_limited()

    gateway = LiteLLMSdkGateway(
        provider_model="openai/agnes-2.5-flash", api_base="", api_key=None, model_alias="paper-default",
        configured_model="agnes-2.5-flash", deployment_id="agnes-primary", recipient="Agnes",
        attempt_seconds=45, attempts_per_request=1, completion=counting,
    )
    with pytest.raises(ModelFailure) as raised:
        complete(gateway)
    assert calls["n"] == 1
    assert len(raised.value.call.attempts) == 1


def test_the_last_failure_decides_the_reported_code():
    errors = [rate_limited(), sdk_error("BadRequestError")]

    with pytest.raises(ModelFailure) as raised:
        complete(build(flaky(errors)))
    assert raised.value.error_code is ErrorCode.UPSTREAM_INVALID_REQUEST
    assert [attempt.error_code for attempt in raised.value.call.attempts] == [
        ErrorCode.UPSTREAM_RATE_LIMITED, ErrorCode.UPSTREAM_INVALID_REQUEST
    ]


def test_an_upstream_retry_after_is_waited_out(monkeypatch):
    """The header is honoured as a real wait, not read and then discarded.

    The wait itself is asserted exactly, because the wall clock is not exact
    here: conftest selects the Windows selector event loop, which wakes from
    ``asyncio.sleep`` a couple of milliseconds early. So the sleep is observed
    where it is requested, and the elapsed time is only checked loosely.
    """

    real_sleep = asyncio.sleep
    requested = []

    async def observed(delay):
        requested.append(delay)
        await real_sleep(delay)

    monkeypatch.setattr(sdk_module.asyncio, "sleep", observed)

    started = time.monotonic()
    with pytest.raises(ModelFailure):
        complete(build(failing(rate_limited(retry_after=0.25))))
    assert requested == [0.25]  # exactly what the upstream asked for
    assert time.monotonic() - started >= 0.2  # and it was really waited out


def test_a_retry_without_retry_after_waits_the_documented_minimum(monkeypatch):
    """The header is optional; its absence is not permission to retry instantly.

    Issue #69 measured the previous behaviour: a 429 with no ``Retry-After`` slept
    for zero seconds, so the "one recovery" was a second request issued
    immediately after the first — precisely what a rate limiter is preventing.
    """

    real_sleep = asyncio.sleep
    requested = []

    async def observed(delay):
        requested.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(sdk_module.asyncio, "sleep", observed)

    with pytest.raises(ModelFailure) as raised:
        complete(build(failing(rate_limited())))

    assert requested == [RECOVERY_BACKOFF_SECONDS]
    assert len(raised.value.call.attempts) == 2, "退避之后仍只恢复一次"
    assert raised.value.error_code is ErrorCode.UPSTREAM_RATE_LIMITED, "失败信号不许被退避改写"


def test_a_retry_after_longer_than_the_task_does_not_burn_the_remaining_budget():
    """Otherwise one upstream header could consume the whole task's time."""

    started = time.monotonic()
    with pytest.raises(ModelFailure) as raised:
        complete(build(failing(rate_limited(retry_after=60))), deadline=time.monotonic() + 30)
    assert time.monotonic() - started < 5
    assert len(raised.value.call.attempts) == 1


def test_recovery_needs_the_task_to_still_have_time():
    """A single request may only recover while the task budget is not spent."""

    with pytest.raises(ContractError) as raised:
        complete(build(slow_failure(rate_limited(), 0.05)), deadline=time.monotonic() + 0.02)
    assert raised.value.error_code is ErrorCode.TASK_TIMEOUT


def test_a_failure_the_sdk_does_not_own_propagates_unchanged():
    """A programming error must not be reported as an upstream failure."""

    with pytest.raises(TypeError):
        complete(build(failing(TypeError("bug"))))


def test_expired_deadline_is_task_timeout_not_an_attempt():
    with pytest.raises(ContractError) as raised:
        complete(build(succeeding()), deadline=time.monotonic() - 1)
    assert raised.value.error_code is ErrorCode.TASK_TIMEOUT


def test_a_completion_without_a_choice_is_an_invalid_request():
    with pytest.raises(ModelFailure) as raised:
        complete(build(succeeding(_Response(choices=False))))
    assert raised.value.error_code is ErrorCode.UPSTREAM_INVALID_REQUEST


def test_the_module_keeps_the_logging_rules_off_by_default():
    """D6 forbids message logging, and the SDK enables it unless told otherwise."""

    assert sdk_module.litellm.turn_off_message_logging is True
    assert sdk_module.litellm.suppress_debug_info is True
    # A remote cost map is a network call at import time; cost is unknown here.
    assert os.environ.get("LITELLM_LOCAL_MODEL_COST_MAP")


def test_a_real_sdk_call_returns_a_call_id_and_usage(monkeypatch):
    """Injected callables cannot prove the SDK entry point itself still behaves."""

    real = sdk_module.litellm.acompletion

    async def mocked(**kwargs):
        return await real(mock_response='{"queries": ["real"]}', **kwargs)

    monkeypatch.setattr(sdk_module.litellm, "acompletion", mocked)
    attempt = complete(build()).call.attempts[0]
    assert attempt.gateway_request_id  # the 36-character LiteLLM call id
    assert attempt.upstream_response_id
    assert attempt.usage is not None and attempt.usage.prompt_tokens is not None


def test_a_real_sdk_failure_reaches_the_same_mapping(monkeypatch):
    real = sdk_module.litellm.acompletion

    async def mocked(**kwargs):
        return await real(mock_response=Exception("boom"), **kwargs)

    monkeypatch.setattr(sdk_module.litellm, "acompletion", mocked)
    with pytest.raises(ModelFailure) as raised:
        complete(build())
    assert raised.value.error_code is ErrorCode.UPSTREAM_UNAVAILABLE


def test_an_aborted_attempt_is_reported_as_cancelled_not_as_a_success():
    """SDK 传输被打断时也要留下这条尝试：取消快收尾不等于这次没发出去（Issue #113）。"""

    async def scenario():
        async def forever(**kwargs):
            await asyncio.sleep(30)

        gateway = build(completion=forever)
        pending = asyncio.ensure_future(gateway.complete(
            "r1", "prompt", time.monotonic() + 300, purpose="query_generation", round_index=0,
            prompt_version="v", context_paragraph_ids=["p:1"],
        ))
        await asyncio.sleep(0.05)
        pending.cancel()
        with pytest.raises(AttemptCancelled) as raised:
            await pending
        return raised.value.call

    call = asyncio.run(scenario())
    assert [(item.status, item.error_code, item.usage) for item in call.attempts] == [("cancelled", None, None)]
