"""Shared read-only HTTP helper for source connectors.

Only fixed official endpoints are used. Every request carries the task deadline;
timeouts take the smaller of the per-request cap and the remaining task budget.
A transient failure is retried at most once, honouring ``Retry-After``; when the
wait exceeds the remaining budget the local wait ends as UPSTREAM_TIMEOUT. The
connectors never follow arbitrary publisher links.
"""

import asyncio
import time

import httpx

from paper_evidence.domain import ContractError, ErrorCode

__all__ = ["Fetcher", "classify_status"]

USER_AGENT = "paper-evidence-agent/0.1 (local verification; mailto:unknown)"


def classify_status(status: int) -> ErrorCode:
    if status in (401, 403):
        return ErrorCode.UPSTREAM_AUTH_FAILED
    if status in (400, 406, 415, 422):
        return ErrorCode.UPSTREAM_INVALID_REQUEST
    if status == 429:
        return ErrorCode.UPSTREAM_RATE_LIMITED
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
                if response.status_code == 429:
                    wait = _retry_after(response)
                    if wait is not None:
                        if deadline is not None and time.monotonic() + wait > deadline:
                            raise ContractError(ErrorCode.UPSTREAM_TIMEOUT, "Retry-After 超过剩余时间")
                        await asyncio.sleep(min(wait, max(0.0, self._remaining(deadline))))
                        continue
            if attempt == 0:
                continue
        assert last is not None
        raise last
