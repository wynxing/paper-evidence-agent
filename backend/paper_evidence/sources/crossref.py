"""Crossref metadata, registration-agency check and the DOI resolver probe.

Follows 技术选型 D9: a Crossref ``/works/{doi}`` 404 is not reported as "DOI does
not exist". The agency endpoint first separates "not Crossref" from "Crossref
record missing"; only an explicit miss from the official DOI resolver means
DOI_UNRESOLVABLE. Authentication, 429, 5xx and timeout remain upstream failures.
"""

import httpx

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.sources.http import Fetcher, classify_status

__all__ = ["CrossrefClient", "DoiResolver"]


def _first(value) -> str | None:
    if isinstance(value, list):
        return value[0] if value else None
    return value if isinstance(value, str) else None


def _year(message: dict) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = (message.get(key) or {}).get("date-parts")
        if parts and parts[0] and isinstance(parts[0][0], int):
            return parts[0][0]
    return None


class CrossrefClient:
    def __init__(self, fetcher: Fetcher, base_url: str, contact_email: str = "") -> None:
        self._fetcher = fetcher
        self._base = base_url.rstrip("/")
        self._mailto = contact_email

    def _params(self) -> dict:
        return {"mailto": self._mailto} if self._mailto else {}

    async def metadata(self, doi: str, deadline: float | None) -> dict | None:
        """Return the Crossref ``message`` object, or None when Crossref has no record."""

        response = await self._fetcher.get(f"{self._base}/works/{doi}", params=self._params(), deadline=deadline)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            # 401/403 是认证失败，不能报成参数错误（术语表「4. 错误码」）。
            raise ContractError(classify_status(response.status_code), "Crossref 元数据响应无效")
        try:
            return response.json()["message"]
        except (ValueError, KeyError) as error:
            raise ContractError(ErrorCode.UPSTREAM_INVALID_REQUEST, "Crossref 元数据协议异常") from error

    async def agency(self, doi: str, deadline: float | None) -> str | None:
        """Return the registration-agency id, or None when it cannot be determined."""

        response = await self._fetcher.get(f"{self._base}/works/{doi}/agency", params=self._params(), deadline=deadline)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            return None
        try:
            return (response.json().get("message") or {}).get("agency", {}).get("id")
        except ValueError:
            return None


class DoiResolver:
    """A non-following probe of the official DOI resolver."""

    def __init__(self, fetcher: Fetcher, base_url: str) -> None:
        self._fetcher = fetcher
        self._base = base_url.rstrip("/")

    async def resolvable(self, doi: str, deadline: float | None) -> bool:
        """True when resolution is confirmed; False only on an explicit miss."""

        response = await self._fetcher.get(f"{self._base}/{doi}", deadline=deadline, follow_redirects=False)
        if response.status_code == 404:
            return False
        if 300 <= response.status_code < 400 or response.status_code == 200:
            return True
        raise ContractError(classify_status(response.status_code), "DOI 解析服务响应异常")
