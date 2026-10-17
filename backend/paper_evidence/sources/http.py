"""Shared read-only HTTP helper for source connectors.

Only fixed official endpoints are used. Every request carries the task deadline;
timeouts take the smaller of the per-request cap and the remaining task budget.
A transient failure is retried at most once, honouring ``Retry-After`` and
otherwise waiting ``RECOVERY_BACKOFF_SECONDS``; when that wait exceeds the
remaining budget the local wait ends as UPSTREAM_TIMEOUT. The connectors never
follow arbitrary publisher links.
"""

import asyncio
import time

import httpx

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.domain.rules import RECOVERY_BACKOFF_SECONDS

__all__ = ["Fetcher", "classify_status"]

USER_AGENT = "paper-evidence-agent/0.1 (local verification; mailto:unknown)"


def classify_status(status: int) -> ErrorCode:
    """Map an HTTP status to a glossary error code.

    ``408`` and ``504`` are timeouts by definition (request timeout / gateway
    timeout), so they are UPSTREAM_TIMEOUT rather than a parameter error or a
    generic unavailability. ``404`` stays UPSTREAM_INVALID_REQUEST on purpose:
    the connectors that can see it either handle it themselves (Crossref, DOI,
    OpenAlex) or are asking a fixed official endpoint that answered "no such
    route" — a broken URL, not a missing upstream. This comment exists so the
    next reader does not "fix" 404 the way 408 was fixed (Issue #69).
    """

    if status in (401, 403):
        return ErrorCode.UPSTREAM_AUTH_FAILED
    if status in (400, 406, 415, 422):
        return ErrorCode.UPSTREAM_INVALID_REQUEST
    if status == 408:
        return ErrorCode.UPSTREAM_TIMEOUT
    if status == 429:
        return ErrorCode.UPSTREAM_RATE_LIMITED
    if status == 504:
        return ErrorCode.UPSTREAM_TIMEOUT
    if status >= 500:
        return ErrorCode.UPSTREAM_UNAVAILABLE
    return ErrorCode.UPSTREAM_INVALID_REQUEST


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class Fetcher:
    """A deadline-aware one-retry GET helper over an injected AsyncClient."""

    def __init__(self, client: httpx.AsyncClient, request_seconds: float, user_agent: str = USER_AGENT) -> None:
        self._client = client
        self._request_seconds = float(request_seconds)
        self._headers = {"User-Agent": user_agent, "Accept": "application/json, application/xml, text/xml, */*"}

    def _remaining(self, deadline: float | None) -> float:
        if deadline is None:
            return self._request_seconds
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ContractError(ErrorCode.UPSTREAM_TIMEOUT, "任务剩余时间不足")
        return remaining

    async def get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        deadline: float | None = None,
        follow_redirects: bool = False,
    ) -> httpx.Response:
        """GET with at most one transient retry; raise ContractError on failure."""

        merged = {**self._headers, **(headers or {})}
        last: ContractError | None = None
        for attempt in range(2):
            remaining = self._remaining(deadline)
            timeout = min(self._request_seconds, remaining)
            requested: float | None = None
            retryable = True
            try:
                response = await self._client.get(
                    url, params=params, headers=merged, timeout=timeout, follow_redirects=follow_redirects
                )
            except (httpx.TimeoutException,) as error:
                last = ContractError(ErrorCode.UPSTREAM_TIMEOUT, f"上游超时：{type(error).__name__}")
            except (httpx.ConnectError, httpx.TransportError, httpx.RemoteProtocolError) as error:
                last = ContractError(ErrorCode.UPSTREAM_UNAVAILABLE, f"上游连接失败：{type(error).__name__}")
            else:
                if response.status_code < 400 or response.status_code in (400, 401, 403, 404, 406, 415, 422):
                    return response
                last = ContractError(classify_status(response.status_code), "上游返回错误状态")
                # Only the documented recovery set is worth a second request:
                # timeouts, throttling and transient 5xx. A 405/409/410 answers the
                # same way the second time, so it ends here rather than after a retry.
                retryable = response.status_code in (408, 429) or response.status_code >= 500
                requested = _retry_after(response) if retryable else None
            if attempt > 0 or not retryable:
                break
            # One recovery, and never immediately (Issue #69). The upstream usually
            # does not say how long to wait — a 429 without ``Retry-After`` is the
            # common case — and firing the second request at once is exactly what a
            # limiter is trying to prevent. ``Retry-After`` still wins when given.
            wait = RECOVERY_BACKOFF_SECONDS if requested is None else requested
            if deadline is not None and time.monotonic() + wait > deadline:
                raise ContractError(ErrorCode.UPSTREAM_TIMEOUT, "退避超过剩余时间")
            await asyncio.sleep(wait)
        if last is None:  # pragma: no cover - every loop exit records a failure first
            raise ContractError(ErrorCode.UPSTREAM_UNAVAILABLE, "上游请求未能完成")
        raise last
